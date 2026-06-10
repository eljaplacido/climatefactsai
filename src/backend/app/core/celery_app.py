"""
Celery Application Instance

Main Celery app for the climatenews modular monolith.
Replaces Kafka-based message queue with Redis/Celery task queue.
"""

import os

from celery import Celery
from .celery_config import get_celery_config

try:
    from shared import request_context, telemetry
except ImportError:
    # Graceful fallback when shared module is not on PYTHONPATH
    request_context = None
    telemetry = None


# Create Celery app instance
app = Celery("climatenews")

# Load configuration from celery_config
app.config_from_object(get_celery_config())

# Best-effort OpenTelemetry bootstrap for worker processes
if telemetry is not None:
    telemetry.init_telemetry(service_name=os.getenv("OTEL_SERVICE_NAME") or "clilens-celery")

# Auto-discover tasks from all task modules
app.autodiscover_tasks([
    "app.tasks.ingestion",
    "app.tasks.processing",
    "app.tasks.video",
    "app.tasks.publication",
    "app.tasks.feed_scheduler",
    "app.tasks.translation",
    "app.tasks.fact_check_pipeline",
    "app.tasks.calibration",
])


# Optional: Add custom task base class for logging/monitoring
from celery import Task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


class LoggingTask(Task):
    """Custom task base class with structured logging."""

    def __call__(self, *args, **kwargs):
        task_id = None
        if isinstance(kwargs.get("task_metadata"), dict):
            task_id = kwargs["task_metadata"].get("task_id")
        if task_id is None and args and isinstance(args[0], dict):
            task_id = args[0].get("task_id")
        if task_id and request_context is not None:
            request_context.set_task_id(str(task_id))

        try:
            from opentelemetry import propagate, trace
            from opentelemetry.trace import SpanKind
        except Exception:
            try:
                return self.run(*args, **kwargs)
            finally:
                if request_context is not None:
                    request_context.set_task_id(None)

        carrier = getattr(self.request, "headers", None) or {}
        ctx = propagate.extract(carrier)
        tracer = trace.get_tracer("clilens.celery")

        with tracer.start_as_current_span(self.name, context=ctx, kind=SpanKind.CONSUMER) as span:
            span.set_attribute("celery.task_id", getattr(self.request, "id", None))
            span.set_attribute("celery.task_name", self.name)
            if task_id:
                span.set_attribute("clilens.task_id", str(task_id))
            try:
                return self.run(*args, **kwargs)
            finally:
                if request_context is not None:
                    request_context.set_task_id(None)

    def on_success(self, retval, task_id, args, kwargs):
        """Log successful task completion."""
        logger.info(
            f"Task {self.name} succeeded",
            extra={
                "task_id": task_id,
                "task_name": self.name,
                "task_args": str(args),
                "task_kwargs": str(kwargs),
            }
        )

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Log task failure."""
        logger.error(
            f"Task {self.name} failed",
            extra={
                "task_id": task_id,
                "task_name": self.name,
                "exception": str(exc),
                "task_args": str(args),
                "task_kwargs": str(kwargs),
            },
            exc_info=einfo
        )

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Log task retry."""
        logger.warning(
            f"Task {self.name} retrying",
            extra={
                "task_id": task_id,
                "task_name": self.name,
                "exception": str(exc),
                "retry_count": self.request.retries,
                "task_args": str(args),
                "task_kwargs": str(kwargs),
            }
        )


# Set custom task base class
app.Task = LoggingTask


# Celery beat schedule (for periodic tasks)
from celery.schedules import crontab

# Multi-country ingestion schedule
# Stagger by 5 minutes per country to avoid API rate limits
_INGESTION_COUNTRIES = os.getenv(
    "INGESTION_COUNTRIES",
    # UN-193 default (2026-05-18): aligned with rss_feed_registry after migration 026.
    # Override per-deploy via INGESTION_COUNTRIES env var if needed.
    "DZ,AO,BJ,BW,BF,BI,CV,CM,CF,TD,KM,CG,CD,CI,DJ,EG,GQ,ER,SZ,ET,GA,GM,GH,GN,GW,KE,LS,LR,LY,MG,MW,ML,MR,MU,MA,MZ,NA,NE,NG,RW,ST,SN,SC,SL,SO,ZA,SS,SD,TZ,TG,TN,UG,ZM,ZW,"
    "AF,AM,AZ,BH,BD,BT,BN,KH,CN,CY,GE,IN,ID,IR,IQ,IL,JP,JO,KZ,KW,KG,LA,LB,MY,MV,MN,MM,NP,KP,OM,PK,PH,QA,SA,SG,KR,LK,SY,TJ,TH,TL,TR,TM,AE,UZ,VN,YE,"
    "AL,AD,AT,BY,BE,BA,BG,HR,CZ,DK,EE,FI,FR,DE,GR,HU,IS,IE,IT,LV,LI,LT,LU,MT,MD,MC,ME,NL,MK,NO,PL,PT,RO,RU,SM,RS,SK,SI,ES,SE,CH,UA,GB,"
    "AG,AR,BS,BB,BZ,BO,BR,CA,CL,CO,CR,CU,DM,DO,EC,SV,GD,GT,GY,HT,HN,JM,MX,NI,PA,PY,PE,KN,LC,VC,SR,TT,US,UY,VE,"
    "AU,FJ,KI,MH,FM,NR,NZ,PW,PG,WS,SB,TO,TV,VU"
).split(",")

app.conf.beat_schedule = {
    # Master scheduler that dispatches per-country tasks
    "scheduled-multi-country-ingestion": {
        "task": "app.tasks.ingestion.scheduled_multi_country_ingestion",
        "schedule": crontab(hour=6, minute=0),  # Run at 6 AM UTC daily
        "kwargs": {},
    },
    # Per-user feed updates — runs every 4 hours, respects tier frequency
    "scheduled-user-feed-updates": {
        "task": "app.tasks.feed_scheduler.update_user_feeds",
        "schedule": crontab(minute=0, hour="*/4"),  # Every 4 hours
        "kwargs": {},
    },
    # Global RSS feed ingestion — every 6 hours
    "scheduled-rss-ingestion": {
        "task": "app.tasks.ingestion.scheduled_rss_ingestion",
        "schedule": crontab(minute=30, hour="*/6"),  # Every 6 hours at :30
        "kwargs": {},
    },
    # RSS feed registry polling — every 30 minutes
    "poll-rss-feeds": {
        "task": "app.tasks.ingestion.poll_rss_feeds",
        "schedule": crontab(minute="*/30"),  # Every 30 minutes
        "kwargs": {},
    },
    # Scientific feed polling — every 6 hours (offset from general RSS)
    "poll-scientific-feeds": {
        "task": "app.tasks.ingestion.scheduled_scientific_feed_ingestion",
        "schedule": crontab(minute=0, hour="*/6"),  # Every 6 hours on the hour
        "kwargs": {},
    },
    # Batch translate recent untranslated articles — every 3 hours
    "batch-translate-recent": {
        "task": "app.tasks.translation.batch_translate_recent",
        "schedule": crontab(minute=15, hour="*/3"),  # Every 3 hours at :15
        "kwargs": {"limit": 20},
    },
    # Automated fact-checking: verify pending articles hourly. No batch_size
    # kwarg — the task reads FACT_CHECK_BATCH_SIZE (default 25) so throughput is
    # tuned in one place (Data-Layer audit 2026-06-10, item 7: was 10/2h, the
    # backlog never drained).
    "auto-verify-pending": {
        "task": "app.tasks.fact_check_pipeline.auto_verify_pending_articles",
        "schedule": crontab(minute=45),  # Every hour at :45
    },
    # Retry failed verifications daily at 4 AM
    "retry-failed-verifications": {
        "task": "app.tasks.fact_check_pipeline.retry_failed_verifications",
        "schedule": crontab(hour=4, minute=0),
        "kwargs": {"batch_size": 5},
    },
    # Pipeline health check every hour
    "pipeline-health-check": {
        "task": "app.tasks.fact_check_pipeline.pipeline_health_check",
        "schedule": crontab(minute=0),  # Every hour on the hour
        "kwargs": {},
    },
    # Calibration refit — nightly at 03:00 UTC, after the day's URL-analysis
    # activity has settled and reviewers have had a chance to label the
    # previous day's outputs. Refits all 3 signals (reliability, agreement,
    # hallucination); a signal with fewer than `min_labels` labels is
    # skipped (logged as insufficient_data) — see Phase 5 wave 7.
    "nightly-calibration-refit": {
        "task": "app.tasks.calibration.nightly_calibration_refit",
        "schedule": crontab(hour=3, minute=0),
        "kwargs": {"min_labels": 5},
    },
}

# Also add individual country schedules staggered by 3 minutes
# With 20 countries: 0, 3, 6, ..., 57 (all within 0-59 minute range)
for _idx, _country in enumerate(_INGESTION_COUNTRIES):
    _country = _country.strip().upper()
    _minute = (_idx * 3) % 60
    _hour_offset = (_idx * 3) // 60  # Overflow into next hour if needed
    if _country:
        app.conf.beat_schedule[f"daily-ingestion-{_country.lower()}"] = {
            "task": "app.tasks.ingestion.discover_articles",
            "schedule": crontab(hour=6 + _hour_offset, minute=_minute),
            "kwargs": {"country": _country, "max_articles": 5},
        }


if __name__ == "__main__":
    app.start()
