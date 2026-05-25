#!/usr/bin/env python
"""Prompt regression harness — Phase 10 Tier-1 (2026-05-25).

Runs every registered prompt against a held-out article set, scores
each output with a judge LLM, and records aggregate scores into the
`prompt_eval_runs` table. The goal: never ship a prompt edit that
quietly degrades quality.

This is INDEPENDENTLY VALUABLE even before any GX10 rollout — it
gives you a baseline pass/fail rate per prompt + per provider that
you can regression-check forever.

Usage:

    # Baseline the current production stack
    python scripts/eval_prompts.py --provider deepseek --sample 100

    # Evaluate a candidate local model
    CLILENS_LOCAL_GX10_BASE_URL=http://gx10.local:8000/v1 \\
      python scripts/eval_prompts.py --provider local-gx10 --sample 100

    # Run only one prompt
    python scripts/eval_prompts.py --prompt-name chat_synthesis_with_actions

    # Use a different judge model
    python scripts/eval_prompts.py --judge-model anthropic

Each run writes one row per prompt to prompt_eval_runs with
mean_score, median_score, pass_rate, error_count + the raw per-sample
results (gzipped JSON) for replay.

Scoring rubric (judge LLM is asked to grade each output 0-100 on):
  - Factual accuracy (does the output match the source article?)
  - JSON / format compliance (when the prompt requires JSON)
  - Relevance (does the output address what was asked?)
  - Hallucination (does the output invent facts not in the source?)

Pass threshold: 70/100 by default; configurable per prompt.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger("eval_prompts")

# Ensure imports work both from repo root and from CWD
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "backend"))

PASS_THRESHOLD = float(os.environ.get("CLILENS_EVAL_PASS_THRESHOLD", "70"))


@dataclass
class EvalSample:
    """One evaluation example: an article + the prompt rendered against it."""
    article_id: str
    article_title: str
    article_text: str
    prompt_template: str
    rendered_prompt: str
    expected_shape: str = "free"  # "json" | "free" | "list"


@dataclass
class EvalResult:
    """One sample's evaluation outcome."""
    sample_idx: int
    article_id: str
    response: Optional[str]
    error: Optional[str]
    latency_ms: int
    judge_score: Optional[float] = None
    judge_verdict: Optional[str] = None
    judge_rationale: Optional[str] = None


@dataclass
class EvalRunSummary:
    prompt_name: str
    prompt_version: Optional[str]
    prompt_fingerprint: Optional[str]
    provider: str
    model: Optional[str]
    sample_size: int
    mean_score: float = 0.0
    median_score: float = 0.0
    pass_rate: float = 0.0
    error_count: int = 0
    notes: str = ""
    raw_results: list[dict] = field(default_factory=list)


JUDGE_SYSTEM = (
    "You are an evaluator grading the quality of an LLM's response to a "
    "prompt. Score 0-100 based on:\n"
    "  - Factual accuracy vs the source text (40 pts)\n"
    "  - Format compliance (JSON-strict if requested) (20 pts)\n"
    "  - Relevance to the prompt's question (20 pts)\n"
    "  - Hallucination penalty: -20 per invented fact (20 pts max)\n\n"
    "Return JSON only: {\"score\": <0-100>, \"verdict\": \"pass\"|\"fail\", "
    "\"rationale\": \"<one sentence>\"}. Pass = score >= 70."
)


def load_sample_articles(sample_size: int) -> list[dict]:
    """Pull a sample of articles directly from the DB. Falls back to a
    hard-coded micro-set when DB is unreachable (CI / local dev).
    """
    try:
        from shared.database import get_postgres
        db = get_postgres()
        rows = db.execute_query(
            """SELECT article_id, title, excerpt, extracted_text
               FROM articles
               WHERE is_synthetic = FALSE
                 AND (extracted_text IS NOT NULL AND LENGTH(extracted_text) > 500)
               ORDER BY created_at DESC
               LIMIT :n""",
            {"n": sample_size},
        )
        if rows:
            return [
                {
                    "article_id": str(r["article_id"]),
                    "title": r["title"],
                    "text": r.get("extracted_text") or r.get("excerpt") or "",
                }
                for r in rows
            ]
    except Exception as exc:
        logger.warning(f"DB sample fetch failed: {exc}")
    return [
        {
            "article_id": "fallback-001",
            "title": "Climate change drives accelerated Arctic warming",
            "text": (
                "The Arctic is warming approximately three times faster than the "
                "global average, according to the latest Arctic Monitoring and "
                "Assessment Programme (AMAP) report. Sea ice extent reached its "
                "second-lowest September minimum on record in 2024, at 4.3 million "
                "km², while Greenland Ice Sheet mass loss continued at "
                "approximately 270 Gt/year between 2002 and 2023."
            ),
        }
    ]


def render_prompts(articles: list[dict], prompt_filter: Optional[str]) -> list[EvalSample]:
    """Use the prompt registry to render each registered prompt against
    each article. Skips prompts not in the filter."""
    from app.domains.intelligence.prompts import PROMPTS

    samples: list[EvalSample] = []
    for prompt_name, prompt in PROMPTS.items():
        if prompt_filter and prompt_filter != prompt_name:
            continue
        for article in articles:
            # Best-effort variable substitution. Real prompts have
            # {context} + {question} placeholders; we feed the article
            # text into context and a stock question.
            try:
                rendered = prompt.template.format(
                    context=article["text"][:4000],
                    question="Summarise the key climate facts in this article.",
                    history="",
                )
            except KeyError:
                # Prompt has variables we don't know about. Skip with a
                # note rather than crashing the harness.
                continue
            samples.append(EvalSample(
                article_id=article["article_id"],
                article_title=article["title"],
                article_text=article["text"][:4000],
                prompt_template=prompt_name,
                rendered_prompt=rendered,
                expected_shape="json" if "JSON" in prompt.template else "free",
            ))
    return samples


def run_one_sample(sample: EvalSample, provider: str) -> EvalResult:
    """Execute one sample through the router + grade it."""
    from app.domains.intelligence.llm_routing import route_chat

    # Force this sample to the requested provider via temp env var.
    env_key = f"CLILENS_{sample.prompt_template.upper()}_PROVIDER"
    old_val = os.environ.get(env_key)
    os.environ[env_key] = provider
    try:
        start = time.time()
        response = route_chat(
            sample.rendered_prompt,
            workload=sample.prompt_template,
            max_tokens=1500,
            temperature=0.1,
        )
        latency_ms = int((time.time() - start) * 1000)
    finally:
        if old_val is None:
            os.environ.pop(env_key, None)
        else:
            os.environ[env_key] = old_val

    if response is None:
        return EvalResult(
            sample_idx=0,
            article_id=sample.article_id,
            response=None,
            error="route_chat returned None",
            latency_ms=latency_ms,
        )

    # Judge step
    judge_response = grade_response(
        article_text=sample.article_text,
        prompt=sample.rendered_prompt[:2000],
        response=response,
    )
    return EvalResult(
        sample_idx=0,
        article_id=sample.article_id,
        response=response,
        error=None,
        latency_ms=latency_ms,
        judge_score=judge_response.get("score"),
        judge_verdict=judge_response.get("verdict"),
        judge_rationale=judge_response.get("rationale"),
    )


def grade_response(article_text: str, prompt: str, response: str) -> dict:
    """Run the judge LLM and parse its verdict."""
    from app.domains.intelligence.llm_routing import route_chat

    judge_prompt = (
        f"SOURCE ARTICLE:\n{article_text[:3000]}\n\n"
        f"PROMPT THAT WAS ASKED:\n{prompt[:1000]}\n\n"
        f"MODEL'S RESPONSE:\n{response[:2500]}\n\n"
        f"Grade this response (0-100). Return JSON only."
    )
    raw = route_chat(
        judge_prompt,
        workload="enrichment",  # judge runs on default workload
        system_prompt=JUDGE_SYSTEM,
        max_tokens=300,
        temperature=0.0,
    )
    if not raw:
        return {"score": None, "verdict": None, "rationale": "judge call failed"}
    try:
        # Strip code fences if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```")[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()
        return json.loads(cleaned)
    except Exception:
        # Best effort: pull a number from the text
        import re
        m = re.search(r"\b(\d{1,3})\b", raw)
        if m:
            score = float(m.group(1))
            return {
                "score": score,
                "verdict": "pass" if score >= PASS_THRESHOLD else "fail",
                "rationale": "parsed from non-JSON response",
            }
        return {"score": 0.0, "verdict": "fail", "rationale": "judge output unparseable"}


def summarise(results: list[EvalResult], prompt_name: str, provider: str) -> EvalRunSummary:
    from app.domains.intelligence.prompts import get_prompt
    try:
        prompt = get_prompt(prompt_name)
        version = prompt.version
        # Fingerprint already computed in prompts.py
        fingerprint = getattr(prompt, "fingerprint", None)
    except Exception:
        version = None
        fingerprint = None

    scores = [r.judge_score for r in results if r.judge_score is not None]
    errors = [r for r in results if r.error is not None]
    passes = sum(1 for s in scores if s >= PASS_THRESHOLD)
    summary = EvalRunSummary(
        prompt_name=prompt_name,
        prompt_version=version,
        prompt_fingerprint=fingerprint,
        provider=provider,
        model=None,
        sample_size=len(results),
        mean_score=(sum(scores) / len(scores)) if scores else 0.0,
        median_score=(sorted(scores)[len(scores) // 2]) if scores else 0.0,
        pass_rate=(passes / len(scores)) if scores else 0.0,
        error_count=len(errors),
        raw_results=[
            {
                "article_id": r.article_id,
                "judge_score": r.judge_score,
                "judge_verdict": r.judge_verdict,
                "judge_rationale": r.judge_rationale,
                "error": r.error,
                "latency_ms": r.latency_ms,
            }
            for r in results
        ],
    )
    return summary


def persist_run(summary: EvalRunSummary) -> None:
    """Write the run summary to prompt_eval_runs table. Best-effort."""
    try:
        from shared.database import get_postgres
        db = get_postgres()
        db.execute_update(
            """INSERT INTO prompt_eval_runs
               (run_id, prompt_name, prompt_version, prompt_fingerprint,
                provider, model, sample_size, mean_score, median_score,
                pass_rate, error_count, notes, raw_results)
               VALUES (:rid, :n, :v, :fp, :p, :m, :ss, :ms, :md, :pr,
                       :ec, :nt, CAST(:raw AS jsonb))""",
            {
                "rid": str(uuid.uuid4()),
                "n": summary.prompt_name,
                "v": summary.prompt_version,
                "fp": summary.prompt_fingerprint,
                "p": summary.provider,
                "m": summary.model,
                "ss": summary.sample_size,
                "ms": summary.mean_score,
                "md": summary.median_score,
                "pr": summary.pass_rate,
                "ec": summary.error_count,
                "nt": summary.notes,
                "raw": json.dumps(summary.raw_results),
            },
        )
    except Exception as exc:
        logger.warning(f"persist_run failed (non-fatal): {exc}")


def print_summary(summary: EvalRunSummary) -> None:
    print()
    print(f"  Prompt:        {summary.prompt_name} ({summary.prompt_version})")
    print(f"  Provider:      {summary.provider}")
    print(f"  Samples:       {summary.sample_size}")
    print(f"  Mean score:    {summary.mean_score:.1f} / 100")
    print(f"  Median score:  {summary.median_score:.1f} / 100")
    print(f"  Pass rate:     {summary.pass_rate * 100:.1f}%  (threshold {PASS_THRESHOLD:.0f})")
    print(f"  Errors:        {summary.error_count}")


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", default="deepseek",
                        help="Provider to evaluate: deepseek|anthropic|openai|local-gx10")
    parser.add_argument("--sample", type=int, default=20,
                        help="Articles per prompt (default 20)")
    parser.add_argument("--prompt-name", default=None,
                        help="Run only this prompt (default: all)")
    parser.add_argument("--no-persist", action="store_true",
                        help="Skip DB write of summary")
    args = parser.parse_args()

    print(f"Loading {args.sample} articles…")
    articles = load_sample_articles(args.sample)
    print(f"Loaded {len(articles)} articles")
    if not articles:
        print("No articles available; aborting.")
        sys.exit(1)

    samples = render_prompts(articles, args.prompt_name)
    print(f"Rendered {len(samples)} samples across "
          f"{len({s.prompt_template for s in samples})} prompt(s)")

    # Group by prompt
    by_prompt: dict[str, list[EvalSample]] = {}
    for s in samples:
        by_prompt.setdefault(s.prompt_template, []).append(s)

    overall_pass = 0
    overall_total = 0
    for prompt_name, prompt_samples in by_prompt.items():
        print(f"\n=== Evaluating {prompt_name} ({len(prompt_samples)} samples) ===")
        results: list[EvalResult] = []
        for i, s in enumerate(prompt_samples):
            print(f"  [{i+1}/{len(prompt_samples)}] {s.article_id[:8]}…",
                  end=" ", flush=True)
            result = run_one_sample(s, args.provider)
            results.append(result)
            print(
                f"score={result.judge_score:.0f}" if result.judge_score is not None
                else f"ERR={result.error[:60] if result.error else 'unknown'}"
            )
        summary = summarise(results, prompt_name, args.provider)
        print_summary(summary)
        overall_pass += int(summary.pass_rate * summary.sample_size)
        overall_total += summary.sample_size
        if not args.no_persist:
            persist_run(summary)

    if overall_total > 0:
        print(f"\nOverall pass rate: {overall_pass / overall_total * 100:.1f}% "
              f"({overall_pass}/{overall_total})")


if __name__ == "__main__":
    main()
