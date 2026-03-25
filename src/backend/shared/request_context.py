"""Request/task context for log correlation.

This module uses contextvars so request-scoped IDs (request_id, task_id, etc.)
can be attached to logs without explicitly threading parameters everywhere.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Optional

_request_id: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
_task_id: ContextVar[Optional[str]] = ContextVar("task_id", default=None)
_user_id: ContextVar[Optional[str]] = ContextVar("user_id", default=None)


def set_request_id(value: Optional[str]) -> None:
    _request_id.set(value)


def get_request_id() -> Optional[str]:
    return _request_id.get()


def set_task_id(value: Optional[str]) -> None:
    _task_id.set(value)


def get_task_id() -> Optional[str]:
    return _task_id.get()


def set_user_id(value: Optional[str]) -> None:
    _user_id.set(value)


def get_user_id() -> Optional[str]:
    return _user_id.get()

