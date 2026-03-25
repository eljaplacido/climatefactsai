"""
Celery task package for the modular monolith workflow.

Modules are auto-discovered in app.core.celery_app.
"""

__all__ = [
    "ingestion",
    "processing",
    "video",
    "publication",
    "translation",
]
