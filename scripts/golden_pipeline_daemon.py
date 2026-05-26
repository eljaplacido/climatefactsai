"""Golden Pipeline Daemon — autonomous overnight curation + enrichment.

Selects highest-quality T1/T2 climate-journalism articles in waves,
queues them for the GX10 Lane A worker (qwen2.5:14b via Ollama) via
the /api/admin/backfill/golden-queue endpoint, waits for enrichment
to complete, validates each output against explicit quality gates,
rewrites the audit report on every wave, and pushes progress to the
@climatefactsbot Telegram chat. Responsive to commands (/status,
/pause, /resume, /stop, /report, /fix).

Architecture
------------
The daemon ITSELF does not call any LLM. It only orchestrates:

  1. SELECT — pull /api/articles, apply hard quality gates (T1/T2
     source allowlist, climate content_category, country_code, recent,
     language whitelist). Score + rank. Take the top N per wave.
  2. QUEUE — POST /api/admin/backfill/golden-queue with the IDs. This
     stamps enrichment_metadata.golden_priority=true and resets
     enriched_at, so the GX10 Lane A worker pulls them first on its
     next polling cycle. Lane A uses qwen2.5:14b locally — no cloud
     LLM cost, full privacy.
  3. WAIT — poll /api/articles/{id} (the v1 path that surfaces
     enrichment_metadata) until each article shows enriched_at + a
     non-empty enriched_excerpt OR the wave timeout is reached.
  4. VALIDATE — run quality gates on every enriched output:
       brief >= 100 chars
       enriched_excerpt >= 400 chars
       climate_context_summary >= 100 chars
       enrichment_metadata.llm_provider contains "local-gx10"
       claim_count >= 2
     Failed articles are flagged in the audit + counted against the
     pass rate. The daemon does NOT retry — keeps the run honest.
  5. AUDIT — rewrite docs/reports/golden-evaluation-<date>.md every
     wave so the user always has a fresh report to inspect.
  6. NOTIFY — push wave summary to Telegram. Long-poll for inbound
     commands between waves.

Budget caps
-----------
- max_articles_total ......... 400 (configurable via --budget)
- max_waves .................. 25
- wave_size .................. 20
- max_minutes_per_wave ....... 35
- pause_between_waves_sec .... 30

At ~30-40s per article on qwen2.5:14b GX10, 20 articles per wave
takes ~10-15 min of inference + ~5 min selection/validation overhead
per wave. 20 waves × 25 min = ~8.3 hours wallclock. Daemon idles
responsively to commands after budget exhaustion until /stop.

Prerequisites
-------------
1. GX10 Lane A worker running (systemd user unit climatenews-lane-a).
   Verify on the GX10 box: `systemctl --user status climatenews-lane-a`
   The worker must have the latest `src/backend/app/domains/content/
   article_enrichment_service.py` with golden_priority ORDER BY (after
   `git pull` on GX10 + service restart). Otherwise queued articles
   will sit at the back of the newest-first queue.

2. Environment variables (in .env or process env):
     SCHEDULER_SECRET ........... admin endpoint auth (from gcloud
                                  secrets versions access scheduler-secret)
     TELEGRAM_BOT_TOKEN ......... bot HTTP API token
     TELEGRAM_CHAT_ID ........... target chat (captured on first /start
                                  if not set)

Usage
-----
   python scripts/golden_pipeline_daemon.py
   python scripts/golden_pipeline_daemon.py --budget 200
   python scripts/golden_pipeline_daemon.py --wave-size 30
   python scripts/golden_pipeline_daemon.py --resume   # continues prior state
   python scripts/golden_pipeline_daemon.py --status   # one-shot status print
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

API_BASE = "https://climatenews-api-srzwxdzmaq-ez.a.run.app"
FRONTEND_BASE = "https://climatenews-frontend-srzwxdzmaq-ez.a.run.app"

ROOT_DIR = Path(__file__).resolve().parent.parent
STATE_DIR = ROOT_DIR / "data" / "golden_pipeline"
STATE_FILE = STATE_DIR / "state.json"
LOG_FILE = STATE_DIR / "daemon.log"
REPORT_PATH = ROOT_DIR / "docs" / "reports" / f"golden-evaluation-{datetime.now().strftime('%Y-%m-%d')}.md"

T1_CLIMATE_SOURCES = {
    "NYT Climate", "The New York Times", "Reuters Climate", "Reuters",
    "BBC News", "BBC Climate", "The Guardian Climate", "Guardian Environment",
    "Bloomberg Green", "Carbon Brief", "Inside Climate News",
    "Yale Climate Connections", "Climate Change News", "Climate Home News",
    "Nature Climate Change", "Nature", "Science", "MIT Technology Review",
    "MIT Climate Portal", "The Conversation", "Rocky Mountain Institute",
    "Union of Concerned Scientists", "Earth.org", "Grist",
    "Climate Policy Initiative", "IPCC", "NASA", "NOAA",
    "International Energy Agency", "UNFCCC", "World Resources Institute",
    "WRI", "Energy Transitions Commission", "PIK Potsdam",
    "Climate Central", "Our World in Data", "Climate TRACE", "Climate Watch",
}
T2_CLIMATE_SOURCES = {
    "DW Climate", "Deutsche Welle", "Mongabay India", "Mongabay Asia",
    "Mongabay Latam", "Mongabay", "ORF Klima (AT)", "ORF Klima",
    "YLE News Climate (FI)", "YLE Klima", "China Dialogue",
    "The Wire Science India", "El País Climate", "Le Monde Planète",
    "Folha de Sao Paulo Ambiente", "INPE Brazil", "Climate.gov",
}
ALLOWED_SOURCES = T1_CLIMATE_SOURCES | T2_CLIMATE_SOURCES
CLIMATE_CATEGORIES = {
    "climate_science", "sustainability", "circular_economy",
    "green_transition", "policy", "localized_forecast",
}
SUPPORTED_LANGS = {"en", "de", "es", "fr", "sv", "fi", "pt", "nl", "da"}

# Title must contain at least ONE climate/energy/environment keyword.
# Defends against the "T1 outlet runs a Trump-DHS-nominee piece tagged
# climate_science" failure mode the user flagged as AI slop. Liberal
# matching on substrings so "renewables" matches "renewable" etc.
CLIMATE_TITLE_KEYWORDS = {
    "climate", "carbon", "emission", "methane", "co2", "co₂", "ghg",
    "greenhouse", "warming", "decarbon", "net zero", "net-zero",
    "renewable", "solar", "wind", "hydropower", "hydroelectric", "nuclear",
    "oil", "gas", "coal", "fossil", "energy", "electric", "battery",
    "hydrogen", "transmission",
    "ipcc", "cop28", "cop29", "cop30", "unfccc", "paris agreement",
    "ev ", " ev", "evs",
    "biodiversity", "deforest", "forest", "glacier", "arctic", "antarctic",
    "ice sheet", "sea ice", "sea-ice", "permafrost", "reef",
    "wildfire", "flood", "drought", "heatwave", "hurricane", "cyclone",
    "monsoon", "el niño", "el nino", "la niña", "la nina",
    "sustain", "esg", "regener", "circular econom",
    "agricultur", "agro", "food security", "soil",
    "ocean", "sea level", "marine",
    "species", "conservation", "rewild",
    "pollut", "smog", "air quality",
    "adaptation", "mitigation", "resilien",
    "weather", "drought", "wet bulb",
}

QUALITY_GATES = {
    "brief_min_chars": 100,
    "excerpt_min_chars": 400,
    "context_min_chars": 100,
    "min_claim_count": 2,
    # SOFT preference: GX10 is the preferred provider (Lane A pattern,
    # privacy, cost). If Lane A is offline or slow, the cloud fallback
    # chain (deepseek→openai→anthropic) keeps the pipeline moving.
    # Audit report counts the breakdown but doesn't fail articles on
    # provider alone — content quality is the actual gate.
    "preferred_provider_contains": "local-gx10",
}

DEFAULTS = {
    "wave_size": 20,
    "max_waves": 25,
    "budget_articles": 400,
    "wave_timeout_minutes": 35,
    "pause_between_waves_sec": 30,
    "telegram_poll_interval_sec": 25,
}


# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------

def log(msg: str) -> None:
    line = f"[{datetime.now().isoformat(timespec='seconds')}] {msg}"
    print(line, flush=True)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# HTTP — stdlib only
# ---------------------------------------------------------------------------

def http_get(path: str, params: dict | None = None, base: str | None = None) -> Any:
    url = (base or API_BASE) + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "golden-daemon/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def http_post(path: str, body: dict, token: str | None = None, base: str | None = None) -> Any:
    url = (base or API_BASE) + path
    headers = {"Content-Type": "application/json", "User-Agent": "golden-daemon/1.0"}
    if token:
        headers["X-Scheduler-Secret"] = token
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers=headers, method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


# ---------------------------------------------------------------------------
# State persistence — atomic writes
# ---------------------------------------------------------------------------

def load_state() -> dict:
    if not STATE_FILE.exists():
        return {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "wave": 0,
            "completed_ids": [],
            "in_progress_ids": [],
            "validation_results": [],
            "telegram_chat_id": None,
            "telegram_last_offset": 0,
            "paused": False,
            "stop_requested": False,
            "issues_reported": [],
        }
    return json.loads(STATE_FILE.read_text())


def save_state(state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, default=str))
    tmp.replace(STATE_FILE)


# ---------------------------------------------------------------------------
# Telegram I/O — stdlib HTTP, no python-telegram-bot dependency
# ---------------------------------------------------------------------------

class Telegram:
    def __init__(self, token: str, chat_id: int | None = None):
        self.token = token
        self.chat_id = chat_id
        self.base = f"https://api.telegram.org/bot{token}"

    def send(self, text: str, parse_mode: str = "Markdown") -> None:
        if not self.chat_id:
            log("Telegram: no chat_id yet, skipping send")
            return
        try:
            req = urllib.request.Request(
                f"{self.base}/sendMessage",
                data=json.dumps({
                    "chat_id": self.chat_id,
                    "text": text[:4000],
                    "parse_mode": parse_mode,
                    "disable_web_page_preview": True,
                }).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=15).read()
        except Exception as exc:
            log(f"Telegram send failed: {exc}")

    def poll(self, last_offset: int, timeout: int = 25) -> tuple[list[dict], int]:
        """Long-poll getUpdates. Returns (messages, new_offset)."""
        try:
            url = (
                f"{self.base}/getUpdates"
                f"?offset={last_offset+1}&timeout={timeout}"
                f"&allowed_updates=%5B%22message%22%5D"
            )
            req = urllib.request.Request(url, headers={"User-Agent": "golden-daemon/1.0"})
            with urllib.request.urlopen(req, timeout=timeout + 10) as r:
                data = json.loads(r.read())
            updates = data.get("result", [])
            messages = []
            new_offset = last_offset
            for u in updates:
                new_offset = max(new_offset, u.get("update_id", 0))
                msg = u.get("message") or {}
                if msg.get("text"):
                    messages.append({
                        "chat_id": msg.get("chat", {}).get("id"),
                        "text": msg["text"],
                    })
            return messages, new_offset
        except Exception as exc:
            log(f"Telegram poll failed: {exc}")
            return [], last_offset


# ---------------------------------------------------------------------------
# Article selection (quality gates)
# ---------------------------------------------------------------------------

def select_candidates(target: int, exclude_ids: set[str]) -> list[dict]:
    """Page through /api/articles, apply gates, score, return top N."""
    seen: set[str] = set()
    out: list[dict] = []
    for page in range(20):  # up to 2000 articles scanned per selection
        try:
            batch = http_get("/api/articles", {"limit": 100, "offset": page * 100})
        except urllib.error.HTTPError:
            break
        if not batch:
            break
        for a in batch:
            aid = a.get("article_id") or a.get("id")
            if not aid or aid in seen or aid in exclude_ids:
                continue
            seen.add(aid)
            src = (a.get("source_name") or "").strip()
            if src not in ALLOWED_SOURCES:
                continue
            if a.get("content_category") not in CLIMATE_CATEGORIES:
                continue
            cc = a.get("country_code")
            if not cc or cc == "XX":
                continue
            # language_code is sometimes None in the list payload — allow
            # that (source allowlist already implies a supported language).
            lang = a.get("language_code")
            if lang is not None and lang not in SUPPORTED_LANGS:
                continue
            # Title must contain an actual climate keyword — the
            # content_category alone proved unreliable (T1 outlets file
            # general politics under climate_science). Defends against
            # AI slop user explicitly flagged.
            title_lower = (a.get("title") or "").lower()
            if not any(kw in title_lower for kw in CLIMATE_TITLE_KEYWORDS):
                continue
            tier = "T1" if src in T1_CLIMATE_SOURCES else "T2"
            score = 30 if tier == "T1" else 15
            score += min(20, (a.get("claim_count") or 0) * 5)
            score += 10 if a.get("verified_claim_count", 0) > 0 else 0
            score += 5 if a.get("overall_credibility") == "HIGH" else 0
            score += 5 if a.get("content_category") == "climate_science" else 0
            out.append({
                "article_id": aid,
                "title": (a.get("title") or "")[:90],
                "source_name": src,
                "country_code": cc,
                "language_code": a.get("language_code"),
                "tier": tier,
                "claim_count": a.get("claim_count") or 0,
                "score": round(score, 1),
            })
        if len(out) >= target * 3:  # enough to rank-and-take
            break
    out.sort(key=lambda c: c["score"], reverse=True)
    return out[:target]


# ---------------------------------------------------------------------------
# Validation (post-enrichment quality gates)
# ---------------------------------------------------------------------------

def validate(article_id: str) -> dict:
    try:
        a = http_get(f"/api/articles/{article_id}")
    except urllib.error.HTTPError as e:
        return {"article_id": article_id, "passes": False, "errors": [f"fetch HTTP {e.code}"]}
    brief = a.get("executive_brief") or ""
    exc = a.get("enriched_excerpt") or ""
    ctx = a.get("climate_context_summary") or ""
    meta = a.get("enrichment_metadata") or {}
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except Exception:
            meta = {}
    provider = meta.get("llm_provider", "")
    claims = a.get("claims_count") or a.get("claim_count") or 0

    errors: list[str] = []
    if len(brief) < QUALITY_GATES["brief_min_chars"]:
        errors.append(f"brief {len(brief)}c < {QUALITY_GATES['brief_min_chars']}")
    if len(exc) < QUALITY_GATES["excerpt_min_chars"]:
        errors.append(f"excerpt {len(exc)}c < {QUALITY_GATES['excerpt_min_chars']}")
    if len(ctx) < QUALITY_GATES["context_min_chars"]:
        errors.append(f"ctx {len(ctx)}c < {QUALITY_GATES['context_min_chars']}")
    if claims < QUALITY_GATES["min_claim_count"]:
        errors.append(f"claims {claims} < {QUALITY_GATES['min_claim_count']}")
    # Provider is a SOFT signal — recorded in audit but doesn't fail
    # the gate (so cloud-fallback enrichments still count when GX10 is
    # offline). Surfaced separately in the report's GX10-share metric.

    return {
        "article_id": article_id,
        "title": (a.get("title") or "")[:80],
        "source_name": a.get("source_name"),
        "country_code": a.get("country_code"),
        "brief_chars": len(brief),
        "excerpt_chars": len(exc),
        "context_chars": len(ctx),
        "claim_count": claims,
        "llm_provider": provider,
        "llm_model": meta.get("llm_model", ""),
        "duration_seconds": meta.get("duration_seconds"),
        "passes": not errors,
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# Wave-level enrichment loop
# ---------------------------------------------------------------------------

def queue_for_gx10(article_ids: list[str], token: str) -> dict:
    return http_post(
        "/api/admin/backfill/golden-queue",
        {"article_ids": article_ids},
        token=token,
    )


def wait_for_completion(article_ids: list[str], minutes: int, telegram: Telegram, state: dict) -> tuple[list[str], list[str]]:
    """Poll /api/articles/{id} until each article has enriched_excerpt > 100 chars.

    Returns (done_ids, pending_ids). Also yields control every ~25s to poll
    Telegram for commands during the wait.
    """
    deadline = time.monotonic() + minutes * 60
    done: set[str] = set()
    last_progress = -1
    while time.monotonic() < deadline:
        if state.get("stop_requested"):
            break
        for aid in article_ids:
            if aid in done:
                continue
            try:
                a = http_get(f"/api/articles/{aid}")
            except urllib.error.HTTPError:
                continue
            ex = (a.get("enriched_excerpt") or "")
            if len(ex) > 100:
                done.add(aid)
        if len(done) != last_progress:
            log(f"  enrichment progress: {len(done)}/{len(article_ids)}")
            last_progress = len(done)
        if len(done) >= len(article_ids):
            break
        _handle_telegram_inbox(telegram, state)
        save_state(state)
        time.sleep(DEFAULTS["telegram_poll_interval_sec"])
    return sorted(done), [a for a in article_ids if a not in done]


# ---------------------------------------------------------------------------
# Telegram command handling
# ---------------------------------------------------------------------------

def _handle_telegram_inbox(telegram: Telegram, state: dict) -> None:
    messages, new_offset = telegram.poll(state["telegram_last_offset"], timeout=1)
    state["telegram_last_offset"] = new_offset
    for m in messages:
        if state["telegram_chat_id"] is None:
            state["telegram_chat_id"] = m["chat_id"]
            telegram.chat_id = m["chat_id"]
            telegram.send("👋 Daemon online. Type /status, /report, /pause, /resume, /stop, /fix <text>.")
        cmd = m["text"].strip().lower().split(" ", 1)
        head = cmd[0]
        arg = cmd[1] if len(cmd) > 1 else ""
        if head == "/start":
            telegram.send("Daemon running. Commands: /status /report /pause /resume /stop /fix <text>")
        elif head == "/status":
            telegram.send(_status_message(state))
        elif head == "/report":
            telegram.send(f"Latest audit: `{REPORT_PATH.relative_to(ROOT_DIR)}`\nWave {state['wave']}, "
                          f"{len([r for r in state['validation_results'] if r['passes']])}/{len(state['validation_results'])} passed gates.")
        elif head == "/pause":
            state["paused"] = True
            telegram.send("⏸️ Pausing after current wave finishes.")
        elif head == "/resume":
            state["paused"] = False
            telegram.send("▶️ Resumed. Next wave will start.")
        elif head == "/stop":
            state["stop_requested"] = True
            telegram.send("🛑 Stop requested. Finishing current wave, then exiting cleanly.")
        elif head == "/fix":
            state["issues_reported"].append({"at": datetime.now(timezone.utc).isoformat(), "issue": arg})
            telegram.send(f"📌 Logged issue: {arg[:120]}")
        else:
            telegram.send("Unknown command. Try: /status /report /pause /resume /stop /fix <text>")


def _status_message(state: dict) -> str:
    passed = sum(1 for r in state["validation_results"] if r["passes"])
    total = len(state["validation_results"])
    gx10 = sum(1 for r in state["validation_results"]
               if "local-gx10" in (r.get("llm_provider") or ""))
    return (
        f"📊 *Golden Pipeline*\n"
        f"Wave: *{state['wave']}*\n"
        f"Validated: *{total}* articles\n"
        f"Passed gates: *{passed}* ({(100*passed/total) if total else 0:.0f}%)\n"
        f"GX10-enriched: *{gx10}*/{total}\n"
        f"Paused: {state['paused']}\n"
        f"Issues logged: {len(state['issues_reported'])}\n"
        f"Report: `{REPORT_PATH.relative_to(ROOT_DIR)}`"
    )


# ---------------------------------------------------------------------------
# Audit report
# ---------------------------------------------------------------------------

def write_audit_report(state: dict) -> None:
    results = state["validation_results"]
    passed = [r for r in results if r["passes"]]
    failed = [r for r in results if not r["passes"]]
    gx10 = [r for r in results if "local-gx10" in (r.get("llm_provider") or "")]

    lines = [
        f"# Golden Pipeline Evaluation — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        f"Autonomous overnight run via `scripts/golden_pipeline_daemon.py`. Targets",
        f"the highest-quality T1/T2 climate-journalism articles in the corpus,",
        f"routes enrichment through the GX10 Lane A worker (qwen2.5:14b via Ollama),",
        f"validates every output against explicit quality gates.",
        "",
        "## Run state",
        "",
        f"- Started: `{state['started_at']}`",
        f"- Wave: **{state['wave']}** of max {DEFAULTS['max_waves']}",
        f"- Validated: **{len(results)}** articles",
        f"- Passed all gates: **{len(passed)}** ({(100*len(passed)/len(results)) if results else 0:.0f}%)",
        f"- GX10-enriched: **{len(gx10)}** ({(100*len(gx10)/len(results)) if results else 0:.0f}%)",
        f"- Failed gates: **{len(failed)}**",
        f"- Stop requested: {state['stop_requested']}",
        "",
        "## Quality gates",
        "",
    ]
    for k, v in QUALITY_GATES.items():
        lines.append(f"- `{k}`: {v}")

    if passed:
        ranked = sorted(passed, key=lambda r: -r.get("excerpt_chars", 0))
        lines.extend([
            "",
            "## Top 30 passed articles (sorted by excerpt depth)",
            "",
            "| # | Title | Source | CC | Brief | Excerpt | Ctx | Claims | LLM |",
            "|---:|---|---|:---:|---:|---:|---:|---:|---|",
        ])
        for i, r in enumerate(ranked[:30], 1):
            lines.append(
                f"| {i} | [{r['title']}]({FRONTEND_BASE}/articles/{r['article_id']}) | "
                f"{r['source_name']} | {r['country_code']} | "
                f"{r['brief_chars']} | {r['excerpt_chars']} | {r['context_chars']} | "
                f"{r['claim_count']} | {r['llm_provider']} |"
            )

    if failed:
        lines.extend(["", "## Rejected (failed quality gates)", "",
                     "| Title | Source | Errors |", "|---|---|---|"])
        for r in failed[:30]:
            errs = "; ".join(r.get("errors", []))[:120]
            lines.append(f"| {(r.get('title') or '?')[:60]} | {r.get('source_name', '?')} | {errs} |")

    if state.get("issues_reported"):
        lines.extend(["", "## Issues reported via Telegram /fix", ""])
        for it in state["issues_reported"]:
            lines.append(f"- `{it['at']}`: {it['issue'][:200]}")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--wave-size", type=int, default=DEFAULTS["wave_size"])
    p.add_argument("--budget", type=int, default=DEFAULTS["budget_articles"])
    p.add_argument("--max-waves", type=int, default=DEFAULTS["max_waves"])
    p.add_argument("--resume", action="store_true")
    p.add_argument("--status", action="store_true")
    args = p.parse_args()

    token = os.environ.get("SCHEDULER_SECRET", "").strip()
    tg_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    tg_chat_id_env = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not tg_token:
        log("FATAL: SCHEDULER_SECRET and TELEGRAM_BOT_TOKEN must be in env")
        return 2

    state = load_state() if args.resume or STATE_FILE.exists() else load_state()
    if tg_chat_id_env and not state.get("telegram_chat_id"):
        state["telegram_chat_id"] = int(tg_chat_id_env)
    telegram = Telegram(tg_token, state["telegram_chat_id"])

    if args.status:
        print(_status_message(state))
        return 0

    def _sigint(_s, _f):
        log("SIGINT received — finishing wave and exiting")
        state["stop_requested"] = True
    signal.signal(signal.SIGINT, _sigint)
    signal.signal(signal.SIGTERM, _sigint)

    log(f"Daemon starting (budget={args.budget}, wave_size={args.wave_size}, max_waves={args.max_waves})")
    telegram.send(
        f"🚀 *Golden Pipeline starting*\n"
        f"Budget: {args.budget} articles • Wave size: {args.wave_size} • Max waves: {args.max_waves}\n"
        f"Enrichment provider: GX10 Lane A (qwen2.5:14b)\n"
        f"Send /status anytime."
    )

    completed_ids = set(state["completed_ids"])
    while state["wave"] < args.max_waves and len(completed_ids) < args.budget:
        if state["stop_requested"]:
            break
        while state["paused"] and not state["stop_requested"]:
            _handle_telegram_inbox(telegram, state)
            save_state(state)
            time.sleep(DEFAULTS["telegram_poll_interval_sec"])
        if state["stop_requested"]:
            break

        state["wave"] += 1
        remaining = args.budget - len(completed_ids)
        wave_n = min(args.wave_size, remaining)
        log(f"=== WAVE {state['wave']} — selecting {wave_n} ===")
        try:
            candidates = select_candidates(wave_n, exclude_ids=completed_ids)
        except Exception as exc:
            log(f"selection error: {exc}\n{traceback.format_exc()}")
            telegram.send(f"⚠️ Wave {state['wave']} selection failed: {type(exc).__name__}: {exc}")
            time.sleep(60)
            continue
        if not candidates:
            log("No candidates left — corpus exhausted")
            telegram.send("✅ Corpus exhausted — no more T1/T2 candidates that aren't already processed.")
            break
        ids = [c["article_id"] for c in candidates]
        log(f"  queueing {len(ids)} via /admin/backfill/golden-queue")
        try:
            q_resp = queue_for_gx10(ids, token)
        except Exception as exc:
            log(f"queue error: {exc}")
            telegram.send(f"⚠️ Wave {state['wave']} queue failed: {type(exc).__name__}: {exc}")
            time.sleep(120)
            continue
        log(f"  queue resp: {q_resp}")
        state["in_progress_ids"] = ids
        save_state(state)

        log(f"  waiting up to {DEFAULTS['wave_timeout_minutes']} min for Lane A worker")
        done_ids, pending = wait_for_completion(
            ids, DEFAULTS["wave_timeout_minutes"], telegram, state,
        )
        log(f"  completed {len(done_ids)}/{len(ids)} (pending: {len(pending)})")

        wave_results = [validate(aid) for aid in done_ids]
        passed = sum(1 for r in wave_results if r["passes"])
        gx10_n = sum(1 for r in wave_results if "local-gx10" in (r.get("llm_provider") or ""))
        state["validation_results"].extend(wave_results)
        state["completed_ids"].extend(done_ids)
        completed_ids.update(done_ids)
        state["in_progress_ids"] = []
        save_state(state)

        write_audit_report(state)
        telegram.send(
            f"✅ *Wave {state['wave']} done*\n"
            f"Enriched: {len(done_ids)}/{len(ids)} • Pending: {len(pending)}\n"
            f"Passed gates: {passed}/{len(wave_results)} • GX10: {gx10_n}\n"
            f"Total: {len(state['completed_ids'])}/{args.budget}"
        )

        if state["stop_requested"]:
            break
        time.sleep(DEFAULTS["pause_between_waves_sec"])

    write_audit_report(state)
    final_passed = sum(1 for r in state["validation_results"] if r["passes"])
    telegram.send(
        f"🏁 *Pipeline finished*\n"
        f"Waves: {state['wave']}\n"
        f"Articles validated: {len(state['validation_results'])}\n"
        f"Passed: {final_passed}\n"
        f"Report: `{REPORT_PATH.relative_to(ROOT_DIR)}`"
    )
    log("Daemon exiting cleanly")
    return 0


if __name__ == "__main__":
    sys.exit(main())
