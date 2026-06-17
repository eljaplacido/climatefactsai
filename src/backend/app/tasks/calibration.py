"""Nightly calibration refit task — Phase 5 wave 7.

Runs `refit_and_persist` over each supported calibration signal once
labels accumulate, so the application picks up an updated Platt fit
without operator intervention. The Cloud Scheduler HTTP endpoint
(`POST /api/methodology/calibration/refit?signal=...`) remains the
manual override; this task is the unattended automation.

Failure mode: if one signal lacks enough labels (default 5), the
refit returns `insufficient_data` and the task moves on. A real
exception in any single signal does NOT abort the rest — each signal
is wrapped in its own try/except so a transient DB blip on one
signal can't block the others.
"""

from __future__ import annotations

from typing import Any, Dict, List

from celery.utils.log import get_task_logger

from app.core.celery_app import app


logger = get_task_logger(__name__)


# Resolved at call time (not module import) so the SUPPORTED_SIGNALS
# tuple from calibration_store remains the single source of truth even
# if a future migration adds a signal.
def _supported_signals() -> List[str]:
    from app.domains.intelligence.calibration_store import SUPPORTED_SIGNALS
    return sorted(SUPPORTED_SIGNALS)


@app.task(
    name="app.tasks.calibration.nightly_calibration_refit",
    bind=True,
    max_retries=2,
    default_retry_delay=600,    # 10 min
)
def nightly_calibration_refit(self, min_labels: int = 5) -> Dict[str, Any]:
    """Refit every supported calibration signal once.

    Returns a summary dict per signal so Celery flower / logs can
    inspect: status (`ok` / `insufficient_data` / `error`), n_labels,
    fit_id, brier_score.

    Idempotent — re-running on the same dataset records the same Platt
    parameters (gradient descent on identical data converges to the
    same fit). Multiple runs per day are safe but wasteful.

    `min_labels` is the floor for triggering a refit on a given signal;
    lower than 5 risks unstable Platt parameters. Override on the call
    site if a deployment has very few labels and wants a placeholder
    fit to show "any calibration at all".
    """
    from shared.database import get_postgres
    from app.domains.intelligence.calibration_store import refit_and_persist

    db = get_postgres()
    out: Dict[str, Any] = {"signals": [], "total_signals": 0, "ok": 0, "insufficient": 0, "errors": 0}

    for signal in _supported_signals():
        out["total_signals"] += 1
        try:
            result = refit_and_persist(db, signal_name=signal, min_labels=int(min_labels))
            row = result.as_dict()
            row["signal"] = signal
            out["signals"].append(row)
            if row.get("status") == "ok":
                out["ok"] += 1
                logger.info(
                    "Calibration refit OK: signal=%s n=%d brier=%s fit_id=%s",
                    signal, row.get("n_labels"), row.get("brier_score"), row.get("fit_id"),
                )
            elif row.get("status") == "insufficient_data":
                out["insufficient"] += 1
                logger.info(
                    "Calibration refit skipped (insufficient labels): signal=%s n=%s min=%d",
                    signal, row.get("n_labels"), min_labels,
                )
            else:
                out["errors"] += 1
                logger.warning(
                    "Calibration refit failed: signal=%s status=%s error=%s",
                    signal, row.get("status"), row.get("error"),
                )
        except Exception as exc:
            out["errors"] += 1
            logger.exception(
                "Calibration refit raised for signal=%s: %s", signal, exc,
            )
            out["signals"].append({
                "signal": signal,
                "status": "error",
                "error": str(exc),
            })

    logger.info(
        "Calibration refit run complete: %d signals (ok=%d insufficient=%d errors=%d)",
        out["total_signals"], out["ok"], out["insufficient"], out["errors"],
    )
    return out
