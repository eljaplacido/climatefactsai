#!/usr/bin/env python3
"""Lane A source assessment worker — runs on the GX10, polls Cloud SQL for
source_credibility_tiers rows missing 3-axis scores (editorial, factcheck,
transparency), analyses each source via Ollama (qwen2.5:7b-instruct), writes
structured scores + reasoning back.

Sibling to lane_a_worker.py (enrichment) and lane_a_entity_worker.py (entity
extraction). Same resident-on-GX10 pattern: GX10 polls Cloud SQL directly
and runs Ollama locally — no Cloud Run ↔ GX10 tunnel needed.

Ratings rubric (0-100 per axis, LLM-assessed from public website analysis):
  Editorial Standards — masthead, corrections policy, named editors, bylines
  Fact-Check Record  — IFCN membership, third-party verification, retractions
  Transparency       — ownership disclosure, funding model, methodology docs

Rate-limited: 1 source per ASSESS_RATE_LIMIT seconds (default 5).
Circuit-breaker: skip sources that fail 3+ consecutive times.
Idempotent: skip sources where all 3 axes are already non-NULL.

Environment variables:
  DATABASE_URL                     Postgres connection (Cloud SQL via proxy / pub IP)
  CLILENS_LOCAL_GX10_BASE_URL      Default: http://localhost:11434/v1
  CLILENS_LOCAL_GX10_API_KEY       Default: "ollama"
  CLILENS_LOCAL_GX10_MODEL         Default: qwen2.5:7b-instruct
  GX10_SOURCE_BATCH_SIZE           Default: 3   (per-cycle batch)
  GX10_SOURCE_IDLE_SLEEP_SEC       Default: 300 (sleep when no work)
  GX10_SOURCE_ASSESS_RATE_LIMIT    Default: 5.0 (seconds between sources)
  GX10_SOURCE_MAX_BATCHES          Default: 0   (0 = forever)
  GX10_SOURCE_CIRCUIT_BREAKER_N    Default: 3   (consecutive failures → skip)
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# Make the repo's shared modules importable. Worker expects to be invoked
# from inside the climatenews repo (cloned to ~/climatenews on GX10).
ROOT_DIR = Path(__file__).resolve().parents[2]
for p in (ROOT_DIR, ROOT_DIR / "src" / "backend"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

os.environ.setdefault("CLILENS_LOCAL_GX10_BASE_URL", "http://localhost:11434/v1")
os.environ.setdefault("CLILENS_LOCAL_GX10_API_KEY", "ollama")
os.environ.setdefault("CLILENS_LOCAL_GX10_MODEL", "qwen2.5:7b-instruct")

from shared.database import get_postgres


def send_telegram(message: str) -> None:
    """Send a brief notification to the Climatefacts bot."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": message[:4000],
            "parse_mode": "Markdown",
        }).encode()
        urllib.request.urlopen(url, data=data, timeout=10)
    except Exception:
        pass  # Never let notifications break the worker


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s | %(message)s",
)
logger = logging.getLogger("lane-a-source-worker")

# --- Tunables -----------------------------------------------------------
BATCH_SIZE = int(os.getenv("GX10_SOURCE_BATCH_SIZE", "3"))
IDLE_SLEEP = int(os.getenv("GX10_SOURCE_IDLE_SLEEP_SEC", "300"))
ASSESS_RATE_LIMIT = float(os.getenv("GX10_SOURCE_ASSESS_RATE_LIMIT", "5.0"))
MAX_BATCHES = int(os.getenv("GX10_SOURCE_MAX_BATCHES", "0"))
CIRCUIT_BREAKER_N = int(os.getenv("GX10_SOURCE_CIRCUIT_BREAKER_N", "3"))

# MODEL is qwen2.5:7b-instruct (lighter than the 14b used for enrichment;
# source assessment is a one-shot structured JSON extraction, not continuous
# prose generation, so 7b is sufficient and keeps more GPU headroom).
OLLAMA_BASE = os.environ["CLILENS_LOCAL_GX10_BASE_URL"]
OLLAMA_MODEL = os.environ["CLILENS_LOCAL_GX10_MODEL"]
TIMEOUT_S = float(os.getenv("CLILENS_LOCAL_GX10_TIMEOUT", "120"))

_shutdown = False


def _handle_signal(signum, _frame):
    global _shutdown
    logger.info("Received signal %s; finishing current source then exiting", signum)
    _shutdown = True


signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)


# ------------------------------------------------------------------
# Prompt template
# ------------------------------------------------------------------

SOURCE_ASSESSMENT_SYSTEM_PROMPT = """You are a media-quality auditor specialised in climate news sources.
Your job is to analyse a news source and produce a structured JSON assessment
with three 0-100 scores plus reasoning for each axis.

Score axes:
  editorial_score (0-100): Editorial standards rigor.
    - Does the source publish editorial guidelines / a standards manual?
    - Is there a named corrections policy?
    - Are articles signed with real author names and credentials?
    - Does the masthead list named editors?

  factcheck_score (0-100): Fact-check engagement.
    - Is the source a verified signatory of the IFCN (International Fact-Checking Network)?
    - Does it partner with third-party fact-checkers (e.g. PolitiFact, Snopes, AFP)?
    - Has it issued public retractions or corrections for major errors?
    - What is its NewsGuard / Media Bias Fact Check rating, if known?

  transparency_score (0-100): Ownership and funding transparency.
    - Does the source disclose its ownership structure publicly?
    - Is its funding model clearly described (nonprofit, ad-supported, subscription)?
    - Does it publish a methodology page for its reporting?
    - Are potential conflicts of interest disclosed?

Rules:
- Scores must be integers in 0-100. Do NOT return floats.
- Be evidence-based. If you cannot find information about an axis, score it
  conservatively (20-40 range) and explain the evidence gap in the reasoning.
- Return ONLY the JSON object below. No markdown fences, no preamble.
- The JSON must have exactly these keys and shapes.

Return format:
{
  "editorial_score": 85,
  "editorial_reasoning": "Published editorial guidelines at /ethics. Named corrections editor. All articles carry bylines with author profiles.",
  "factcheck_score": 70,
  "factcheck_reasoning": "Not IFCN-verified but partners with AFP Fact Check for climate claims. One notable retraction in 2023.",
  "transparency_score": 60,
  "transparency_reasoning": "Ownership disclosed as nonprofit 501(c)(3). Funding sources listed but methodology page is sparse.",
  "overall_notes": "Reliable climate outlet with solid editorial standards. Fact-checking is outsourced rather than in-house."
}
"""


def _build_user_prompt(source_name: str, domain: str, website_url: str, tier: str, existing_notes: str) -> str:
    fmt = [f"SOURCE NAME: {source_name}"]
    if domain:
        fmt.append(f"DOMAIN: {domain}")
    if website_url:
        fmt.append(f"WEBSITE: {website_url}")
    if tier:
        fmt.append(f"CURRENT TIER: {tier}")
    if existing_notes:
        fmt.append(f"EXISTING NOTES: {existing_notes}")
    fmt.append(
        "\nAnalyse this source across the three axes (editorial, factcheck, transparency). "
        "Produce the JSON assessment now."
    )
    return "\n".join(fmt)


# ------------------------------------------------------------------
# LLM call
# ------------------------------------------------------------------

async def _assess_source(
    client: Any,
    source_name: str,
    domain: str,
    website_url: str,
    tier: str,
    existing_notes: str,
) -> Optional[Dict[str, Any]]:
    """Call Ollama with the assessment prompt, return parsed JSON dict or None."""
    user_prompt = _build_user_prompt(source_name, domain, website_url, tier, existing_notes)

    import httpx as _httpx
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": SOURCE_ASSESSMENT_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": 1200},
    }

    try:
        async with _httpx.AsyncClient(timeout=TIMEOUT_S) as hc:
            r = await hc.post(
                f"{OLLAMA_BASE}/chat/completions",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            r.raise_for_status()
            body = r.json()
    except Exception as exc:
        logger.error("Ollama call failed for source %s: %s", source_name, exc)
        return None

    choice = (body.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    raw = (message.get("content") or "").strip()

    if not raw:
        logger.warning("Ollama returned empty content for source %s", source_name)
        return None

    # Strip markdown fences if present
    if raw.startswith("```"):
        lines = raw.split("\n")
        # Remove first fence line and last fence line
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw = "\n".join(lines).strip()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning(
            "JSON parse failed for source %s: %s. Raw (first 300 chars): %s",
            source_name, exc, raw[:300],
        )
        return None

    return result


# ------------------------------------------------------------------
# Validation
# ------------------------------------------------------------------

def _validate_assessment(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Clamp scores, require all 3 axes present, fill missing reasoning."""
    required = ("editorial_score", "factcheck_score", "transparency_score")
    for key in required:
        if key not in data:
            logger.warning("Assessment missing required key: %s", key)
            return None

    cleaned: Dict[str, Any] = {}
    for axis in required:
        raw = data.get(axis)
        try:
            score = int(float(raw))
        except (TypeError, ValueError):
            logger.warning("Non-numeric score for %s: %r", axis, raw)
            return None
        cleaned[axis] = max(0, min(100, score))

    cleaned["editorial_reasoning"] = str(data.get("editorial_reasoning") or "")[:2000]
    cleaned["factcheck_reasoning"] = str(data.get("factcheck_reasoning") or "")[:2000]
    cleaned["transparency_reasoning"] = str(data.get("transparency_reasoning") or "")[:2000]
    cleaned["overall_notes"] = str(data.get("overall_notes") or "")[:2000]

    return cleaned


# ------------------------------------------------------------------
# Polling
# ------------------------------------------------------------------

def _fetch_pending_sources(db) -> list:
    """Return list of source_credibility_tiers rows missing any 3-axis score."""
    rows = db.execute_query(
        """SELECT source_name, domain, website_url, tier, notes,
                  editorial_score, factcheck_score, transparency_score
           FROM source_credibility_tiers
           WHERE (editorial_score IS NULL
                  OR factcheck_score IS NULL
                  OR transparency_score IS NULL)
           ORDER BY
               CASE WHEN tier = 'T1' THEN 0
                    WHEN tier = 'T2' THEN 1
                    WHEN tier = 'T3' THEN 2
                    ELSE 3
               END,
               source_name ASC
           LIMIT :lim""",
        {"lim": BATCH_SIZE},
    )
    return rows or []


def _write_scores(
    db,
    source_name: str,
    editorial_score: int,
    factcheck_score: int,
    transparency_score: int,
    editorial_reasoning: str,
    factcheck_reasoning: str,
    transparency_reasoning: str,
    overall_notes: str,
) -> None:
    """Persist 3-axis scores + reasoning back to source_credibility_tiers."""
    full_notes = (
        f"[CLILENS auto-scored] Editorial: {editorial_reasoning} | "
        f"Factcheck: {factcheck_reasoning} | "
        f"Transparency: {transparency_reasoning}"
    )
    if overall_notes.strip():
        full_notes += f" | {overall_notes}"

    # Keep existing notes if present, prepend new assessment
    # Build a JSON evidence blob for the scoring_rationale column if it exists
    # (best-effort — column added in mig 041 / 045 series)
    evidence = json.dumps(
        {
            "editorial_score": editorial_score,
            "editorial_reasoning": editorial_reasoning,
            "factcheck_score": factcheck_score,
            "factcheck_reasoning": factcheck_reasoning,
            "transparency_score": transparency_score,
            "transparency_reasoning": transparency_reasoning,
            "overall_notes": overall_notes,
            "assessed_by": "clilens-lane-a-source-worker",
            "model": OLLAMA_MODEL,
            "assessed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
        ensure_ascii=False,
    )

    db.execute_update(
        """UPDATE source_credibility_tiers
           SET editorial_score = :ed,
               factcheck_score = :fc,
               transparency_score = :tr,
               notes = CASE
                   WHEN notes IS NOT NULL AND notes <> ''
                   THEN notes || ' | ' || :new_notes
                   ELSE :new_notes
               END,
               scoring_last_reviewed_at = NOW()
           WHERE source_name = :name""",
        {
            "ed": editorial_score,
            "fc": factcheck_score,
            "tr": transparency_score,
            "new_notes": full_notes,
            "name": source_name,
        },
    )


# ------------------------------------------------------------------
# Main loop
# ------------------------------------------------------------------

async def main() -> int:
    db = get_postgres()

    logger.info(
        "Lane A source worker starting | batch=%s idle=%ss rate_limit=%ss "
        "model=%s ollama=%s circuit_breaker_n=%s",
        BATCH_SIZE, IDLE_SLEEP, ASSESS_RATE_LIMIT, OLLAMA_MODEL, OLLAMA_BASE,
        CIRCUIT_BREAKER_N,
    )

    # Sanity: Ollama reachable?
    import httpx as _httpx
    try:
        async with _httpx.AsyncClient(timeout=10.0) as hc:
            r = await hc.get(f"{OLLAMA_BASE}/models")
            r.raise_for_status()
        logger.info("Ollama reachable at %s", OLLAMA_BASE)
    except Exception as exc:
        logger.error("Ollama unreachable at startup: %s", exc)
        return 2

    # Verify the model is pulled
    try:
        async with _httpx.AsyncClient(timeout=10.0) as hc:
            r = await hc.get(f"{OLLAMA_BASE}/models")
            models = r.json().get("models", [])
            model_names = [m.get("name", "") for m in models]
            if not any(OLLAMA_MODEL in mn or mn.startswith(OLLAMA_MODEL) for mn in model_names):
                logger.warning(
                    "Model %s not found in Ollama model list %s — "
                    "first run may trigger a pull on-demand",
                    OLLAMA_MODEL, model_names[:5],
                )
    except Exception:
        pass

    # Circuit breaker state: {source_name: consecutive_failures}
    breaker: Dict[str, int] = {}

    batches_run = 0
    consecutive_empty = 0

    while not _shutdown:
        batches_run += 1
        rows = []
        try:
            rows = _fetch_pending_sources(db)
        except Exception as exc:
            logger.error("DB poll failed: %s", exc, exc_info=True)
            await asyncio.sleep(min(IDLE_SLEEP, 60))
            continue

        if not rows:
            consecutive_empty += 1
            sleep_s = min(IDLE_SLEEP * (2 ** min(consecutive_empty - 1, 5)), 1800)
            logger.info(
                "No unscored sources; sleeping %ss (empty streak %s)",
                sleep_s, consecutive_empty,
            )
            await asyncio.sleep(sleep_s)
            if MAX_BATCHES and batches_run >= MAX_BATCHES:
                logger.info("Hit MAX_BATCHES=%s; exiting cleanly", MAX_BATCHES)
                break
            continue

        consecutive_empty = 0
        processed = 0
        failed = 0
        skipped = 0
        circuit_skipped = 0

        # Reuse a single httpx client for the batch
        import httpx as _httpx

        for row in rows:
            if _shutdown:
                break

            source_name = str(row.get("source_name") or "")
            if not source_name:
                skipped += 1
                continue

            # Idempotency: double-check scores are still NULL in this row
            row_ed = row.get("editorial_score")
            row_fc = row.get("factcheck_score")
            row_tr = row.get("transparency_score")
            if row_ed is not None and row_fc is not None and row_tr is not None:
                skipped += 1
                continue

            # Circuit breaker
            fail_count = breaker.get(source_name, 0)
            if fail_count >= CIRCUIT_BREAKER_N:
                circuit_skipped += 1
                logger.info(
                    "Circuit-breaker skip | source=%s failures=%s threshold=%s",
                    source_name, fail_count, CIRCUIT_BREAKER_N,
                )
                continue

            # Rate limit
            if processed + failed > 0:
                await asyncio.sleep(ASSESS_RATE_LIMIT)

            domain = str(row.get("domain") or "")
            website_url = str(row.get("website_url") or "")
            tier = str(row.get("tier") or "unknown")
            existing_notes = str(row.get("notes") or "")

            logger.info(
                "Assessing source | name=%s domain=%s tier=%s",
                source_name, domain, tier,
            )

            async with _httpx.AsyncClient(timeout=TIMEOUT_S + 10) as hc:
                assessment = await _assess_source(
                    hc,
                    source_name=source_name,
                    domain=domain,
                    website_url=website_url,
                    tier=tier,
                    existing_notes=existing_notes,
                )

            if assessment is None:
                breaker[source_name] = fail_count + 1
                failed += 1
                logger.warning(
                    "Source assessment failed | name=%s attempts=%s",
                    source_name, fail_count + 1,
                )
                continue

            validated = _validate_assessment(assessment)
            if validated is None:
                breaker[source_name] = fail_count + 1
                failed += 1
                logger.warning(
                    "Source assessment validation failed | name=%s attempts=%s",
                    source_name, fail_count + 1,
                )
                continue

            # Write back to DB
            try:
                _write_scores(
                    db,
                    source_name=source_name,
                    editorial_score=validated["editorial_score"],
                    factcheck_score=validated["factcheck_score"],
                    transparency_score=validated["transparency_score"],
                    editorial_reasoning=validated["editorial_reasoning"],
                    factcheck_reasoning=validated["factcheck_reasoning"],
                    transparency_reasoning=validated["transparency_reasoning"],
                    overall_notes=validated["overall_notes"],
                )
                # Successful write → reset circuit breaker
                breaker.pop(source_name, None)
                processed += 1
                logger.info(
                    "Source scored | name=%s editorial=%s factcheck=%s transparency=%s",
                    source_name,
                    validated["editorial_score"],
                    validated["factcheck_score"],
                    validated["transparency_score"],
                )
                send_telegram(
                    f"🏛️ Scored source {source_name} "
                    f"(E:{validated['editorial_score']}/"
                    f"F:{validated['factcheck_score']}/"
                    f"T:{validated['transparency_score']})"
                )
            except Exception as exc:
                breaker[source_name] = fail_count + 1
                failed += 1
                logger.error(
                    "DB write failed for source %s: %s",
                    source_name, exc,
                )

        logger.info(
            "Batch %s done | processed=%s failed=%s skipped=%s "
            "circuit_skipped=%s total_found=%s",
            batches_run, processed, failed, skipped, circuit_skipped, len(rows),
        )

        if MAX_BATCHES and batches_run >= MAX_BATCHES:
            logger.info("Hit MAX_BATCHES=%s; exiting cleanly", MAX_BATCHES)
            break

        await asyncio.sleep(2)

    logger.info(
        "Lane A source worker stopped after %s batches | "
        "sources in circuit-breaker: %s",
        batches_run, len(breaker),
    )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
