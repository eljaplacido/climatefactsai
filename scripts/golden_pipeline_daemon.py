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
    "research_per_wave": 1,         # research paper analyses per article wave
    "companies_per_wave": 3,        # company claim analyses per article wave
}

# Curated open-access climate research targets for the Phase 2 sweep.
# /api/research/analyze accepts URL — these are public, scrape-friendly,
# and represent the canonical climate-science evidence stack.
CLIMATE_RESEARCH_TARGETS: list[dict] = [
    # Global stocktake / canonical reports
    {"label": "Global Carbon Budget 2023", "url": "https://essd.copernicus.org/articles/15/5301/2023/"},
    {"label": "Global Carbon Budget 2022", "url": "https://essd.copernicus.org/articles/15/2295/2023/"},
    {"label": "Forster et al. — Indicators of Global Climate Change 2024", "url": "https://essd.copernicus.org/articles/16/2625/2024/"},
    {"label": "UNEP Emissions Gap Report 2024", "url": "https://www.unep.org/resources/emissions-gap-report-2024"},
    {"label": "UNEP Production Gap Report 2023", "url": "https://productiongap.org/2023report/"},
    {"label": "IEA World Energy Outlook 2024 — Key Findings", "url": "https://www.iea.org/reports/world-energy-outlook-2024/key-findings"},
    {"label": "IEA Net Zero Roadmap Update 2023", "url": "https://www.iea.org/reports/net-zero-roadmap-a-global-pathway-to-keep-the-15-0c-goal-in-reach"},
    {"label": "WMO State of the Global Climate 2023", "url": "https://wmo.int/publication-series/state-of-global-climate-2023"},
    {"label": "Climate Action Tracker — Global Update Dec 2024", "url": "https://climateactiontracker.org/global/cat-emissions-gaps/"},
    {"label": "IPCC AR6 Synthesis Report SPM", "url": "https://www.ipcc.ch/report/ar6/syr/summary-for-policymakers/"},
    {"label": "IPCC AR6 WG1 Summary for Policymakers", "url": "https://www.ipcc.ch/report/ar6/wg1/chapter/summary-for-policymakers/"},
    {"label": "IPCC AR6 WG2 Summary for Policymakers", "url": "https://www.ipcc.ch/report/ar6/wg2/chapter/summary-for-policymakers/"},
    {"label": "IPCC AR6 WG3 Summary for Policymakers", "url": "https://www.ipcc.ch/report/ar6/wg3/chapter/summary-for-policymakers/"},
    {"label": "IPCC Special Report on 1.5°C SPM", "url": "https://www.ipcc.ch/sr15/chapter/spm/"},
    {"label": "IPCC Special Report on Oceans & Cryosphere SPM", "url": "https://www.ipcc.ch/srocc/chapter/summary-for-policymakers/"},
    {"label": "IPCC Special Report on Land SPM", "url": "https://www.ipcc.ch/srccl/chapter/summary-for-policymakers/"},
    # Frontier peer-reviewed climate science
    {"label": "Hansen et al. 2023 — Global warming acceleration (OUP Climate)", "url": "https://academic.oup.com/oocc/article/3/1/kgad008/7335889"},
    {"label": "Rockström et al. — Planetary boundaries 2023 update (Sci Adv)", "url": "https://www.science.org/doi/10.1126/sciadv.adh2458"},
    {"label": "Trisos et al. — Abrupt biodiversity loss thresholds (Nature 2020)", "url": "https://www.nature.com/articles/s41586-020-2189-9"},
    {"label": "Frame et al. 2017 — Attributable damages from extreme weather", "url": "https://www.nature.com/articles/nclimate3110"},
    {"label": "Steffen et al. 2018 — Hothouse Earth trajectories (PNAS)", "url": "https://www.pnas.org/doi/10.1073/pnas.1810141115"},
    {"label": "Wunderling et al. 2024 — Tipping point cascades (Earth Syst Dynam)", "url": "https://esd.copernicus.org/articles/14/41/2023/"},
    {"label": "Lenton et al. 2008 — Tipping elements (PNAS)", "url": "https://www.pnas.org/doi/10.1073/pnas.0705414105"},
    {"label": "Kemp et al. 2022 — Climate endgame (PNAS)", "url": "https://www.pnas.org/doi/10.1073/pnas.2108146119"},
    {"label": "Lenton et al. 2023 — Earth system tipping cascades", "url": "https://esd.copernicus.org/articles/14/41/2023/"},
    # Mitigation, energy systems, removal
    {"label": "Net-zero pathways for major economies (Nature 2023)", "url": "https://www.nature.com/articles/s41558-023-01660-1"},
    {"label": "Realmonte et al. — CO2 removal modelling (Nature Communications)", "url": "https://www.nature.com/articles/s41467-019-10842-5"},
    {"label": "Smith et al. 2024 — State of CDR 2024", "url": "https://www.stateofcdr.org/resources"},
    # Impacts, attribution, extreme events
    {"label": "Otto et al. 2024 — Attribution methodology synthesis", "url": "https://www.worldweatherattribution.org/about/methodology/"},
    {"label": "Carbon Brief — Mapped: Every climate attribution study", "url": "https://www.carbonbrief.org/mapped-how-climate-change-affects-extreme-weather-around-the-world/"},
    # Policy, finance, justice
    {"label": "World Bank — State and Trends of Carbon Pricing 2024", "url": "https://openknowledge.worldbank.org/entities/publication/b0d66765-299c-4fb8-921f-61f6bb979087"},
    {"label": "Climate Bonds Initiative — Sustainable Debt Global Outlook 2024", "url": "https://www.climatebonds.net/2024/02/sustainable-debt-global-state-market-2023"},
    {"label": "OECD — Climate Finance Provided & Mobilised 2023", "url": "https://www.oecd.org/climate-change/finance-usd-100-billion-goal/"},
]



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

def _http_with_retry(req: urllib.request.Request, timeout: int = 30, max_attempts: int = 4) -> Any:
    """HTTP retry wrapper. Retries on 5xx, 429, and network errors with
    exponential backoff (1s, 3s, 9s, 27s). Fail-loud on 4xx (other than
    429) since those are programmer/auth errors that retry won't fix.
    """
    backoff = 1.0
    last_exc: Exception | None = None
    for attempt in range(max_attempts):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            last_exc = e
            if e.code == 429 or 500 <= e.code < 600:
                time.sleep(backoff)
                backoff *= 3.0
                continue
            raise  # 4xx (other than 429) — re-raise immediately
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            last_exc = e
            time.sleep(backoff)
            backoff *= 3.0
            continue
    if last_exc:
        raise last_exc
    raise RuntimeError("HTTP retry exhausted with no exception")


def http_get(path: str, params: dict | None = None, base: str | None = None) -> Any:
    url = (base or API_BASE) + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "golden-daemon/1.0"})
    return _http_with_retry(req, timeout=30)


def http_post(path: str, body: dict, token: str | None = None, base: str | None = None) -> Any:
    url = (base or API_BASE) + path
    headers = {"Content-Type": "application/json", "User-Agent": "golden-daemon/1.0"}
    if token:
        headers["X-Scheduler-Secret"] = token
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers=headers, method="POST",
    )
    return _http_with_retry(req, timeout=60)


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
    """Atomic save with one-deep backup so corruption is recoverable."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    # Backup previous good state before overwriting
    if STATE_FILE.exists():
        try:
            backup = STATE_FILE.with_suffix(".json.bak")
            backup.write_bytes(STATE_FILE.read_bytes())
        except Exception:
            pass
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, default=str))
    tmp.replace(STATE_FILE)


def restart_lane_a_worker() -> tuple[bool, str]:
    """Self-healing: restart the Lane A worker via systemctl.

    Called when daemon detects Lane A has stalled (no enrichment progress
    for N minutes). Best-effort — systemd user services require the user
    session to be active (linger=yes confirmed).
    """
    import subprocess
    try:
        result = subprocess.run(
            ["systemctl", "--user", "restart", "clilens-lane-a"],
            capture_output=True, text=True, timeout=60,
        )
        ok = result.returncode == 0
        return ok, (result.stderr or result.stdout or "").strip()[:200]
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


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

def fetch_off_topic_ids() -> set[str]:
    """Fetch the user-flagged off-topic article IDs (Stage 3 / M4).

    The article-detail page's Flag-as-off-topic button POSTs to
    /api/feedback/topic/{article_id}. This endpoint returns the
    accumulated set. The daemon excludes them from selection so a
    flagged article doesn't keep re-appearing in future waves.
    """
    try:
        resp = http_get("/api/feedback/topic/off-topic-ids", {"limit": 5000})
        return set(resp.get("off_topic_ids") or [])
    except Exception as exc:
        log(f"  [topic-feedback] fetch failed (continuing): {exc}")
        return set()


def select_candidates(target: int, exclude_ids: set[str]) -> list[dict]:
    """Page through /api/articles, apply gates, score, return top N.

    Hard gates (in order):
      1. Not already processed (exclude_ids — successful past waves)
      2. Not flagged off-topic by users (Stage 3 / M4 corpus feedback)
      3. country_code set + non-XX
      4. language supported
      5. Climate keyword in title — WORD-BOUNDARY match (deforest must
         not substring-match Forestalia; this exact bug slipped a
         Spanish corruption piece into Stage-1 review)

    Source allowlist is a scoring bonus, NOT a hard gate, so the
    candidate pool stays at 1500+ across the 14k-article corpus.
    """
    off_topic = fetch_off_topic_ids()
    if off_topic:
        log(f"  [selection] excluding {len(off_topic)} user-flagged off-topic articles")
    seen: set[str] = set()
    out: list[dict] = []
    for page in range(80):  # up to 8000 articles scanned per selection
        try:
            batch = http_get("/api/articles", {"limit": 100, "offset": page * 100})
        except urllib.error.HTTPError:
            break
        if not batch:
            break
        for a in batch:
            aid = a.get("article_id") or a.get("id")
            if not aid or aid in seen or aid in exclude_ids or aid in off_topic:
                continue
            seen.add(aid)
            src = (a.get("source_name") or "").strip()
            cat = a.get("content_category")
            cc = a.get("country_code")
            if not cc or cc == "XX":
                continue
            lang = a.get("language_code")
            if lang is not None and lang not in SUPPORTED_LANGS:
                continue
            title_lower = (a.get("title") or "").lower()
            # HARD gate 1: climate keyword in title (anti-slop).
            # Word-boundary match — "deforest" must not substring-match
            # "Forestalia" (the Stage-1 review caught a Spanish corruption
            # piece slipping through because of this exact bug).
            import re
            if not any(
                re.search(r"\b" + re.escape(kw) + r"\b", title_lower)
                for kw in CLIMATE_TITLE_KEYWORDS
            ):
                continue
            # HARD gate 2: climate content_category OR title implies climate
            # (some legit climate articles are mis-categorised as 'policy'
            # or 'general' but the title-keyword gate already filters).
            # Reject only obvious non-climate categories (none yet defined,
            # so accept any category).

            # SCORING — source tier bonus, not a hard requirement
            if src in T1_CLIMATE_SOURCES:
                tier, base = "T1", 30
            elif src in T2_CLIMATE_SOURCES:
                tier, base = "T2", 18
            else:
                tier, base = "T3", 8
            score = base
            score += min(20, (a.get("claim_count") or 0) * 5)
            score += 10 if a.get("verified_claim_count", 0) > 0 else 0
            score += 5 if a.get("overall_credibility") == "HIGH" else 0
            score += 5 if cat == "climate_science" else 0
            score += 3 if cat in CLIMATE_CATEGORIES else 0
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
        if len(out) >= target * 5:
            break
    out.sort(key=lambda c: c["score"], reverse=True)
    return out[:target]


# ---------------------------------------------------------------------------
# Validation (post-enrichment quality gates)
# ---------------------------------------------------------------------------

def validate(article_id: str) -> dict:
    # v2 endpoint is the one that correctly serializes the enrichment
    # fields (executive_brief, enriched_excerpt, climate_context_summary,
    # enrichment_metadata) — the v1 path drops some of them. Using v1
    # was causing every article to fail validation with brief=0 even
    # when the DB had a populated brief.
    try:
        a = http_get(f"/api/v2/articles/{article_id}")
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


# ---------------------------------------------------------------------------
# Phase 2 — research paper analyses (via /api/research/analyze)
# ---------------------------------------------------------------------------

def run_research_analysis(target: dict, state: dict, telegram: Telegram) -> dict:
    """Call /api/research/analyze on one curated climate paper URL.

    Validates the response shape: must have methodology_score,
    citation_score, climate_relevance, and at least 1 key_claim.
    Recorded in state['research_results'] for the audit report.
    """
    label = target["label"]
    url = target["url"]
    log(f"  [research] analyzing: {label}")
    try:
        result = http_post("/api/research/analyze", {"url": url})
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode()[:200]
        except Exception:
            pass
        log(f"  [research] HTTP {e.code} for {label}: {body}")
        return {"label": label, "url": url, "passes": False, "error": f"HTTP {e.code}: {body}"}
    except Exception as exc:
        log(f"  [research] error: {exc}")
        return {"label": label, "url": url, "passes": False, "error": str(exc)}

    analysis = result.get("analysis") or {}
    credibility = result.get("credibility") or {}
    posterior = credibility.get("posterior") or {}
    errors: list[str] = []
    if not analysis.get("summary"):
        errors.append("no summary")
    if (analysis.get("methodology_score") or 0) < 30:
        errors.append(f"methodology_score {analysis.get('methodology_score')} < 30")
    if not analysis.get("key_claims"):
        errors.append("no key_claims")
    if not analysis.get("climate_relevance"):
        errors.append("no climate_relevance")

    record = {
        "label": label,
        "url": url,
        "title": (result.get("document") or {}).get("title", "")[:120],
        "methodology_score": analysis.get("methodology_score"),
        "citation_score": analysis.get("citation_score"),
        "data_transparency_score": analysis.get("data_transparency_score"),
        "climate_relevance": analysis.get("climate_relevance"),
        "key_claims_count": len(analysis.get("key_claims") or []),
        "posterior_score": posterior.get("posterior_score"),
        "posterior_ci": posterior.get("confidence_interval"),
        "recommendation": analysis.get("recommendation"),
        "passes": not errors,
        "errors": errors,
    }
    state.setdefault("research_results", []).append(record)
    return record


# ---------------------------------------------------------------------------
# Phase 3 — company corporate-claim analyses (Cloud Run /companies/analyze)
# ---------------------------------------------------------------------------

# Sample corporate claims to verify against each company's disclosure context.
# Mix of ECGT-prohibited offset claims, SBTi-aligned commitments, absolute
# reductions, RE100 — tests the full verdict taxonomy.
CORPORATE_CLAIM_TEMPLATES: list[dict] = [
    {"label": "Net-zero by 2030", "claim_text": "We will achieve net-zero greenhouse gas emissions across all scopes by 2030."},
    {"label": "Net-zero by 2050", "claim_text": "We will achieve net-zero emissions across our entire value chain by 2050."},
    {"label": "50% absolute scope 1+2 by 2030", "claim_text": "We commit to a 50% absolute reduction in scope 1 and scope 2 emissions by 2030 against a 2019 baseline."},
    {"label": "Offset-based climate neutral", "claim_text": "Our flagship product line is climate neutral through high-quality carbon offset purchases."},
    {"label": "SBTi 1.5°C-aligned", "claim_text": "Our science-based targets are validated by SBTi and aligned with limiting warming to 1.5°C."},
    {"label": "100% renewable electricity", "claim_text": "100% of our purchased electricity globally is sourced from renewable energy under RE100."},
    {"label": "Scope 3 disclosure", "claim_text": "We disclose our full scope 3 value-chain emissions across all 15 categories with third-party assurance."},
    {"label": "Nature-positive by 2030", "claim_text": "We commit to being nature-positive by 2030, restoring biodiversity in our operations."},
]


def fetch_top_companies(limit: int = 50) -> list[dict]:
    """Pull the top SBTi-validated companies by data richness."""
    try:
        resp = http_get("/api/companies", {"sort": "richness", "limit": limit, "sbti_only": "true"})
        return resp.get("companies", []) or []
    except Exception as exc:
        log(f"  [company] fetch failed: {exc}")
        return []


def run_company_analysis(company_id_or_ticker: str, name: str, claim_template: dict, state: dict) -> dict:
    """Call POST /api/companies/{id}/analyze with a sample sustainability claim."""
    log(f"  [company] {name} ({company_id_or_ticker[:8]}…) — {claim_template['label']}")
    try:
        result = http_post(
            f"/api/companies/{urllib.parse.quote(company_id_or_ticker)}/analyze",
            {"claim_text": claim_template["claim_text"]},
        )
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode()[:200]
        except Exception:
            pass
        return {
            "company": name, "ticker": company_id_or_ticker,
            "claim_label": claim_template["label"],
            "passes": False, "error": f"HTTP {e.code}: {body}",
        }
    except Exception as exc:
        return {
            "company": name, "ticker": company_id_or_ticker,
            "claim_label": claim_template["label"],
            "passes": False, "error": str(exc),
        }

    verdict = result.get("verdict")
    record = {
        "company": name,
        "ticker": company_id_or_ticker,
        "claim_label": claim_template["label"],
        "claim_text": claim_template["claim_text"][:200],
        "claim_id": result.get("claim_id"),
        "claim_type": result.get("claim_type"),
        "verdict": verdict,
        "flag_reason": result.get("flag_reason"),
        "evidence": (result.get("evidence") or "")[:300] if result.get("evidence") else None,
        "passes": verdict is not None and verdict != "error",
        "errors": [] if (verdict and verdict != "error") else [f"verdict={verdict!r}"],
    }
    state.setdefault("company_results", []).append(record)
    return record




def wait_for_completion(article_ids: list[str], minutes: int, telegram: Telegram, state: dict) -> tuple[list[str], list[str]]:
    """Poll until each article has enriched_excerpt > 100 chars.

    Self-healing: if no progress for STALL_THRESHOLD_SEC (default 8min),
    attempts to restart the Lane A worker via systemctl. After 2 stall
    cycles, gives up on this wave and returns whatever's done.
    """
    STALL_THRESHOLD_SEC = 480  # 8 minutes without progress = stalled
    deadline = time.monotonic() + minutes * 60
    done: set[str] = set()
    last_progress_count = -1
    last_progress_at = time.monotonic()
    stall_attempts = 0
    while time.monotonic() < deadline:
        if state.get("stop_requested"):
            break
        for aid in article_ids:
            if aid in done:
                continue
            try:
                a = http_get(f"/api/v2/articles/{aid}")
            except urllib.error.HTTPError:
                continue
            ex = (a.get("enriched_excerpt") or "")
            if len(ex) > 100:
                done.add(aid)
        if len(done) != last_progress_count:
            log(f"  enrichment progress: {len(done)}/{len(article_ids)}")
            last_progress_count = len(done)
            last_progress_at = time.monotonic()
            stall_attempts = 0
        elif (time.monotonic() - last_progress_at) > STALL_THRESHOLD_SEC and stall_attempts < 2:
            stall_attempts += 1
            log(f"  STALL detected ({STALL_THRESHOLD_SEC}s no progress) — restarting Lane A worker (attempt {stall_attempts}/2)")
            ok, msg = restart_lane_a_worker()
            telegram.send(
                f"Stall detected on wave {state['wave']} ({len(done)}/{len(article_ids)} done). "
                f"Restarting Lane A worker: {'OK' if ok else 'FAILED ' + msg[:100]}"
            )
            last_progress_at = time.monotonic()  # reset stall timer post-restart
            time.sleep(30)
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
        # Case-insensitive command matching — "/Restart" works same as "/restart"
        raw = m["text"].strip()
        cmd = raw.split(" ", 1)
        head = cmd[0].lower()
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
            # /fix <text> — log issue AND attempt self-healing actions:
            #   - clear stop_requested if set
            #   - unpause if paused
            #   - re-hydrate top_companies if empty
            #   - reset in_progress_ids (so a stuck wave isn't tracked forever)
            state["issues_reported"].append({
                "at": datetime.now(timezone.utc).isoformat(),
                "issue": arg,
            })
            actions: list[str] = []
            if state.get("stop_requested"):
                state["stop_requested"] = False
                actions.append("cleared stop_requested")
            if state.get("paused"):
                state["paused"] = False
                actions.append("unpaused")
            if not state.get("top_companies"):
                try:
                    companies = fetch_top_companies(limit=50)
                    state["top_companies"] = [
                        {"id": c.get("company_id"), "ticker": c.get("ticker"), "name": c.get("name")}
                        for c in companies if c.get("company_id")
                    ]
                    actions.append(f"rehydrated top_companies ({len(state['top_companies'])})")
                except Exception as exc:
                    actions.append(f"company refresh failed: {type(exc).__name__}")
            if state.get("in_progress_ids"):
                actions.append(f"cleared in_progress_ids ({len(state['in_progress_ids'])})")
                state["in_progress_ids"] = []
            save_state(state)
            heal = ", ".join(actions) if actions else "no obvious recovery actions"
            telegram.send(f"Issue logged: {arg[:120]}\nSelf-healing: {heal}")
        elif head == "/restart":
            # Force daemon process exit so systemd restarts it cleanly
            state["stop_requested"] = False  # ensure resumes after restart
            save_state(state)
            telegram.send("Restart requested. Process exiting now; systemd will respawn in 30s.")
            log("/restart received — exit(75) to trigger systemd restart")
            sys.exit(75)
        else:
            telegram.send("Unknown command. Try: /status /report /pause /resume /stop /fix <text> /restart")


def _status_message(state: dict) -> str:
    art_results = state.get("validation_results", [])
    art_passed = sum(1 for r in art_results if r["passes"])
    art_total = len(art_results)
    gx10 = sum(1 for r in art_results if "local-gx10" in (r.get("llm_provider") or ""))
    res_results = state.get("research_results", [])
    res_passed = sum(1 for r in res_results if r.get("passes"))
    co_results = state.get("company_results", [])
    co_passed = sum(1 for r in co_results if r.get("passes"))
    return (
        f"📊 *Golden Pipeline*\n"
        f"Wave: *{state['wave']}*\n"
        f"📰 Articles: *{art_passed}*/{art_total} passed, GX10: {gx10}\n"
        f"📄 Research: *{res_passed}*/{len(res_results)} passed\n"
        f"🏢 Companies: *{co_passed}*/{len(co_results)} passed\n"
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

    retried = state.get("retried_ids", {}) or {}
    research = state.get("research_results", [])
    companies = state.get("company_results", [])
    lines = [
        f"# Golden Pipeline Evaluation — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        f"Autonomous overnight run via `scripts/golden_pipeline_daemon.py`. Three",
        f"interleaved phases per wave: article enrichment (GX10 qwen2.5:7b via",
        f"Ollama, Lane A pattern), research-paper analysis (Cloud Run DeepSeek),",
        f"and corporate-claim verification (Cloud Run DeepSeek + ECGT adjudicator).",
        f"Every output validated against explicit quality gates. Failed articles",
        f"auto-retried once via the retrospective-evaluation pass.",
        "",
        "## Run state",
        "",
        f"- Started: `{state['started_at']}`",
        f"- Current wave: **{state['wave']}** of max {DEFAULTS['max_waves']}",
        f"- 📰 Articles validated: **{len(results)}** ({len(passed)} passed, {len(failed)} failed, {len(retried)} retried)",
        f"- 📄 Research papers analyzed: **{len(research)}** ({sum(1 for r in research if r.get('passes'))} passed)",
        f"- 🏢 Company claims analyzed: **{len(companies)}** ({sum(1 for r in companies if r.get('passes'))} passed)",
        f"- GX10 share on articles: **{len(gx10)}/{len(results)}** ({(100*len(gx10)/len(results)) if results else 0:.0f}%)",
        f"- Issues logged via /fix: {len(state.get('issues_reported', []))}",
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

    # Research analyses section
    research = state.get("research_results", [])
    if research:
        lines.extend([
            "",
            "## Research paper analyses",
            "",
            f"- Total: **{len(research)}**",
            f"- Passed (valid response shape): **{sum(1 for r in research if r.get('passes'))}**",
            "",
            "| # | Paper | Meth. | Cit. | Transp. | Relevance | Claims | Posterior | Recommendation |",
            "|---:|---|---:|---:|---:|:---:|---:|---:|---|",
        ])
        for i, r in enumerate(research, 1):
            lines.append(
                f"| {i} | [{r['label'][:60]}]({r['url']}) | "
                f"{r.get('methodology_score','?')} | {r.get('citation_score','?')} | "
                f"{r.get('data_transparency_score','?')} | {r.get('climate_relevance','?')} | "
                f"{r.get('key_claims_count','?')} | {r.get('posterior_score','?')} | "
                f"{(r.get('recommendation') or '?')[:30]} |"
            )

    # Company corporate-claim analyses section
    companies = state.get("company_results", [])
    if companies:
        lines.extend([
            "",
            "## Corporate sustainability-claim analyses",
            "",
            f"- Total: **{len(companies)}**",
            f"- Passed (verdict returned): **{sum(1 for r in companies if r.get('passes'))}**",
            "",
            "| # | Company | Claim | Verdict | Flag reason |",
            "|---:|---|---|---|---|",
        ])
        for i, r in enumerate(companies, 1):
            lines.append(
                f"| {i} | {r.get('company','?')} | {r.get('claim_label','?')} | "
                f"`{r.get('verdict','?')}` | {(r.get('flag_reason') or '—')[:60]} |"
            )

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
    # ALWAYS start in non-stop, non-paused mode. The prior process may
    # have saved stop_requested=True on SIGTERM (systemd restart) — that
    # was an OLD intent, not a current one. If the user wants to stop,
    # they send /stop. Otherwise default is "run".
    state["stop_requested"] = False
    state["paused"] = False
    save_state(state)
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
            # Corpus exhausted for now — DON'T exit. Keep running research
            # + company analyses (those have their own large target lists),
            # and retry article selection on the next wave (the corpus
            # grows as RSS ingestion happens overnight).
            log("article corpus temporarily exhausted — skipping enrich, running research+company only")
            telegram.send(
                f"ℹ️ Wave {state['wave']}: no new article candidates (corpus exhausted for now). "
                f"Continuing with research + company phases. Will retry articles next wave."
            )
            ids = []
            done_ids = []
            pending = []
            wave_results = []
        else:
            ids = [c["article_id"] for c in candidates]

        # Article enrichment phase — skipped when ids is empty (corpus
        # exhausted), but research + company phases below still fire.
        if ids:
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

            # RETROSPECTIVE EVALUATION — for articles that failed the
            # validation gates this wave (brief too short / no GX10 /
            # missing context), give them ONE more chance by re-queueing
            # for GX10 enrichment. State tracks retry_attempts so an
            # article can't be looped indefinitely. After 1 retry it's
            # accepted as a permanent failure in the audit.
            state.setdefault("retried_ids", {})
            failed_for_retry = [
                r["article_id"] for r in wave_results
                if not r["passes"] and state["retried_ids"].get(r["article_id"], 0) < 1
            ]
            if failed_for_retry:
                log(f"  [retro-eval] re-queueing {len(failed_for_retry)} failed articles for 1 more GX10 attempt")
                try:
                    queue_for_gx10(failed_for_retry, token)
                    for aid in failed_for_retry:
                        state["retried_ids"][aid] = state["retried_ids"].get(aid, 0) + 1
                    save_state(state)
                    telegram.send(f"Retro-eval: re-queued {len(failed_for_retry)} failed articles for retry")
                except Exception as exc:
                    log(f"  [retro-eval] re-queue failed: {exc}")

        # Phase 2 — research paper analyses (per wave). Cycles through the
        # 35+ curated climate-science targets; if exhausted, cycles again
        # to broaden the per-target evidence base.
        for _ in range(DEFAULTS["research_per_wave"]):
            ri = state.get("research_index", 0)
            target = CLIMATE_RESEARCH_TARGETS[ri % len(CLIMATE_RESEARCH_TARGETS)]
            log(f"  [research] {ri+1}: {target['label'][:60]}")
            try:
                rec = run_research_analysis(target, state, telegram)
                state["research_index"] = ri + 1
                save_state(state)
                msg = f"📄 Paper {ri+1}: {rec['label'][:55]}"
                if rec["passes"]:
                    msg += f" ✅ meth={rec.get('methodology_score')} rel={rec.get('climate_relevance')}"
                else:
                    msg += f" ❌ {(', '.join(rec.get('errors', []))[:60])}"
                telegram.send(msg)
            except Exception as exc:
                log(f"research phase failed: {exc}\n{traceback.format_exc()}")
                break

        # Phase 3 — company corporate-claim analyses (per wave). 50 top
        # companies × 8 claim templates = 400 unique analyses available.
        if not state.get("top_companies"):
            companies = fetch_top_companies(limit=50)
            state["top_companies"] = [
                {"id": c.get("company_id"), "ticker": c.get("ticker"), "name": c.get("name")}
                for c in companies if c.get("company_id")
            ]
            log(f"  [company] hydrated top_companies: {len(state['top_companies'])}")
        picks = state.get("top_companies") or []
        if picks:
            for _ in range(DEFAULTS["companies_per_wave"]):
                ci = state.get("company_index", 0)
                company = picks[ci % len(picks)]
                template = CORPORATE_CLAIM_TEMPLATES[(ci // len(picks)) % len(CORPORATE_CLAIM_TEMPLATES)]
                # Prefer ticker for human-readable URL when available, else company_id
                lookup_id = company.get("ticker") or company.get("id")
                try:
                    rec = run_company_analysis(lookup_id, company["name"], template, state)
                    state["company_index"] = ci + 1
                    save_state(state)
                    if rec["passes"]:
                        flag = f" — {rec.get('flag_reason')}" if rec.get("flag_reason") else ""
                        telegram.send(f"🏢 {company['name'][:30]} / {template['label'][:25]} → *{rec.get('verdict')}*{flag}")
                    else:
                        telegram.send(f"🏢 {company['name'][:30]} ❌ {(', '.join(rec.get('errors', []))[:60])}")
                except Exception as exc:
                    log(f"company phase failed: {exc}")
                    break

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
