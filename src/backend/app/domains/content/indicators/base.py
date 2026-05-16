"""Indicator adapter base class + records.

Every primary-source adapter (Climate TRACE, OWID, CAT, WB CCKP, UNFCCC NDC,
IRENA) implements `IndicatorAdapter.fetch_records()` to yield
`IndicatorRecord` objects. The base class handles upsert into
`country_indicators` with full provenance and returns a `SyncResult` for
the calling Celery task / CLI command to log.

Design choices anchored to the audit's truth-machine axes:

  * Reliability — Adapters fail individually, never silently. A failed
    record raises; the sync wraps it in `SyncResult.errors` so partial
    progress is preserved.

  * Transparency — `methodology_url` (from `indicator_definitions`) and
    `methodology_version` (per-record) both surface to the user. The raw
    record is kept verbatim in `country_indicators.raw_record`.

  * Traceability — `source_url` on every row points to the exact fetch
    URL (not just the base API). Re-deriving a value 6 months later is a
    SQL query, not a forensic investigation.

  * Calibration — `uncertainty_low` / `uncertainty_high` carry the
    source's own uncertainty bands when published; downstream scoring
    propagates these as confidence intervals rather than point estimates.

  * Robustness — `UNIQUE (country_code, indicator_id, year, source_name)`
    enforces idempotent sync; a re-fetch of the same data produces no
    duplicate rows. Schema drift in upstream payloads is logged as
    `SyncResult.errors` rather than silently dropped.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional

_logger = logging.getLogger("indicators")


@dataclass(frozen=True)
class IndicatorRecord:
    """One country-year-indicator value, fully attributed.

    Adapters yield these; the base class upserts. `raw_record` is the
    parsed source payload (JSON-serialisable) — kept verbatim so a future
    auditor can recompute the displayed `value` from the original data.
    """
    country_code: str           # ISO 3166-1 alpha-2; capitalised on insert
    indicator_id: str           # FK to indicator_definitions.indicator_id
    year: int
    value: Optional[float]
    source_url: str             # exact fetch URL, not the base API
    uncertainty_low: Optional[float] = None
    uncertainty_high: Optional[float] = None
    methodology_version: Optional[str] = None
    raw_record: Optional[Dict[str, Any]] = None


@dataclass
class SyncResult:
    """Outcome of a single adapter sync run. Surfaced to operators / audit log."""
    source_name: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    fetched_count: int = 0
    upserted_count: int = 0
    skipped_count: int = 0
    errors: List[str] = field(default_factory=list)

    @property
    def duration_seconds(self) -> Optional[float]:
        if self.finished_at is None:
            return None
        return (self.finished_at - self.started_at).total_seconds()

    def as_dict(self) -> Dict[str, Any]:
        return {
            "source_name": self.source_name,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "duration_seconds": self.duration_seconds,
            "fetched_count": self.fetched_count,
            "upserted_count": self.upserted_count,
            "skipped_count": self.skipped_count,
            "errors": self.errors,
        }


class IndicatorAdapter(ABC):
    """Base class for primary-source climate indicator adapters."""

    # Subclasses set these as class attributes.
    source_name: str = ""
    methodology_url: str = ""

    # Optional: subclass may set a default User-Agent for the HTTP client.
    default_user_agent: str = "CliLens.AI/1.0 (+https://clilens.ai)"

    def __init__(self) -> None:
        if not self.source_name:
            raise ValueError(
                f"{self.__class__.__name__} must set `source_name`"
            )

    # ------------------------------------------------------------------
    # Subclass contract
    # ------------------------------------------------------------------

    @abstractmethod
    async def fetch_records(self) -> AsyncIterator[IndicatorRecord]:
        """Yield IndicatorRecord objects for upsert.

        Subclasses raise on unrecoverable errors (network down, schema
        completely changed). Per-record schema variance should be tolerated
        with a debug log + skip; the base class's sync() will then count
        the skips in SyncResult.skipped_count.

        Implemented as `async def` returning `AsyncIterator[IndicatorRecord]`
        so adapters can stream large payloads (Climate TRACE has thousands
        of records per fetch).
        """
        # `yield` to make this an async generator on the type level;
        # the actual implementation lives in subclasses.
        if False:
            yield IndicatorRecord(  # pragma: no cover
                country_code="",
                indicator_id="",
                year=0,
                value=None,
                source_url="",
            )

    # ------------------------------------------------------------------
    # Sync runner (called by Celery task / CLI)
    # ------------------------------------------------------------------

    async def sync(self, db) -> SyncResult:
        """Fetch records, upsert into country_indicators, return SyncResult.

        Idempotent on the natural key (country, indicator, year, source):
        re-running on the same upstream payload produces zero new rows.
        """
        result = SyncResult(source_name=self.source_name, started_at=datetime.utcnow())

        try:
            async for record in self.fetch_records():
                result.fetched_count += 1
                try:
                    self._upsert(db, record)
                    result.upserted_count += 1
                except Exception as exc:
                    msg = (
                        f"{self.source_name} upsert failed for "
                        f"({record.country_code}, {record.indicator_id}, "
                        f"{record.year}): {exc}"
                    )
                    _logger.warning(msg)
                    result.errors.append(msg)
                    result.skipped_count += 1
        except Exception as exc:
            # Network down, auth failure, schema completely wrong, etc.
            msg = f"{self.source_name} fetch aborted: {exc}"
            _logger.error(msg)
            result.errors.append(msg)
        finally:
            result.finished_at = datetime.utcnow()

        _logger.info(
            "Indicator sync complete: %s | fetched=%d upserted=%d "
            "skipped=%d errors=%d duration=%.1fs",
            self.source_name,
            result.fetched_count,
            result.upserted_count,
            result.skipped_count,
            len(result.errors),
            result.duration_seconds or 0.0,
        )
        return result

    # ------------------------------------------------------------------
    # Internal: upsert one record
    # ------------------------------------------------------------------

    def _upsert(self, db, record: IndicatorRecord) -> None:
        """Idempotent INSERT … ON CONFLICT DO UPDATE on the natural key.

        Updates `value`, `uncertainty_*`, `fetched_at`,
        `methodology_version`, `raw_record` — never touches the natural
        key columns. `source_url` is updated so each fetch records the
        most recent retrieval URL.
        """
        import json as _json

        raw_json = _json.dumps(record.raw_record) if record.raw_record is not None else None

        db.execute_update(
            """
            INSERT INTO country_indicators (
                country_code, indicator_id, year, value,
                uncertainty_low, uncertainty_high,
                source_name, source_url, fetched_at,
                methodology_version, raw_record
            ) VALUES (
                :country_code, :indicator_id, :year, :value,
                :uncertainty_low, :uncertainty_high,
                :source_name, :source_url, NOW(),
                :methodology_version, CAST(:raw_record AS jsonb)
            )
            ON CONFLICT (country_code, indicator_id, year, source_name)
            DO UPDATE SET
                value               = EXCLUDED.value,
                uncertainty_low     = EXCLUDED.uncertainty_low,
                uncertainty_high    = EXCLUDED.uncertainty_high,
                source_url          = EXCLUDED.source_url,
                fetched_at          = EXCLUDED.fetched_at,
                methodology_version = EXCLUDED.methodology_version,
                raw_record          = EXCLUDED.raw_record
            """,
            {
                "country_code": record.country_code.upper()[:2],
                "indicator_id": record.indicator_id,
                "year": record.year,
                "value": record.value,
                "uncertainty_low": record.uncertainty_low,
                "uncertainty_high": record.uncertainty_high,
                "source_name": self.source_name,
                "source_url": record.source_url,
                "methodology_version": record.methodology_version,
                "raw_record": raw_json,
            },
        )
