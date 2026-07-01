"""Regression guard for launch-blocker ML-01 — full-text search config.

ROOT CAUSE (ML-01): migration 018 built articles.search_tsv with
`to_tsvector(clilens_lang_cfg(language_code), …)`. language_code is mislabelled
'fi' on ~all rows, so every stored lexeme was Finnish-stemmed, while every query
site used `websearch_to_tsquery('simple', …)`. The two configs never agreed, so
keyword search matched 0 articles platform-wide (GET /api/search/?q=climate -> []).

FIX: migration 072 rebuilt search_tsv on a FIXED 'english' config, and every
query site was pinned to `websearch_to_tsquery('english', …)`. Both sides now
share the identical config.

This module pins that fix so the class of regression (a query site drifting back
to 'simple', or the vector rebuild losing its fixed 'english' config) can't
silently reappear. It is fully deterministic — no live DB required.
"""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import MagicMock

REPO_ROOT = Path(__file__).resolve().parents[2]

# Every source tree that issues FTS queries against articles.search_tsv.
_CODE_DIRS = [
    REPO_ROOT / "api",
    REPO_ROOT / "src" / "backend" / "app",
]

# Files that are known to run FTS queries — each MUST use the 'english' config.
_KNOWN_FTS_FILES = [
    REPO_ROOT / "api" / "chat_routes.py",
    REPO_ROOT / "api" / "main.py",
    REPO_ROOT / "api" / "saved_query_routes.py",
    REPO_ROOT / "api" / "search_routes.py",
    REPO_ROOT / "api" / "map" / "routes_query.py",
    REPO_ROOT / "api" / "map" / "routes_main.py",
    REPO_ROOT / "src" / "backend" / "app" / "domains" / "content" / "repository.py",
    REPO_ROOT / "src" / "backend" / "app" / "domains" / "intelligence" / "cross_article_service.py",
    REPO_ROOT / "src" / "backend" / "app" / "domains" / "intelligence" / "hybrid_rag_service.py",
    REPO_ROOT / "src" / "backend" / "app" / "domains" / "intelligence" / "semantic_query_service.py",
]

_SIMPLE_CALL = re.compile(r"websearch_to_tsquery\(\s*'simple'")
_ENGLISH_CALL = re.compile(r"websearch_to_tsquery\(\s*'english'")


def _iter_py_files():
    for base in _CODE_DIRS:
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            yield path


def test_no_code_query_site_uses_simple_config():
    """No product code may query search_tsv with the 'simple' config.

    'simple' on the query side matched 0 rows against the 'english'-built
    search_tsv column — the exact ML-01 failure mode.
    """
    offenders = [
        str(path.relative_to(REPO_ROOT))
        for path in _iter_py_files()
        if _SIMPLE_CALL.search(path.read_text(encoding="utf-8"))
    ]
    assert not offenders, (
        "websearch_to_tsquery('simple', …) found in product code — the stored "
        "search_tsv is built on the 'english' config (migration 072), so a "
        f"'simple' query matches nothing. Offending files: {offenders}"
    )


def test_every_fts_file_uses_english_config():
    """Each known FTS query site pins the 'english' config on the query side."""
    for path in _KNOWN_FTS_FILES:
        assert path.exists(), f"expected FTS file missing: {path}"
        text = path.read_text(encoding="utf-8")
        assert _ENGLISH_CALL.search(text), (
            f"{path.relative_to(REPO_ROOT)} no longer uses "
            f"websearch_to_tsquery('english', …) — FTS query/stored config drift."
        )
        assert not _SIMPLE_CALL.search(text), (
            f"{path.relative_to(REPO_ROOT)} still uses the 'simple' config."
        )


def test_hybrid_rag_fulltext_builder_emits_english_config():
    """The HybridRAG FTS builder emits SQL bound to the 'english' config.

    Exercises the real query builder (no DB) so a config regression is caught
    functionally, not just by a source scan.
    """
    from app.domains.intelligence.hybrid_rag_service import HybridRAGService

    db = MagicMock()
    db.execute_query.return_value = []
    svc = HybridRAGService(db)

    svc._fulltext_search("climate", limit=5)

    call = db.execute_query.call_args
    sql = call.args[0] if call.args else call.kwargs.get("query", "")
    params = call.args[1] if len(call.args) > 1 else call.kwargs.get("params", {})

    assert "a.search_tsv" in sql
    assert _ENGLISH_CALL.search(sql), "FTS builder must use the 'english' config"
    assert not _SIMPLE_CALL.search(sql), "FTS builder must not use the 'simple' config"
    # User text is bound, never interpolated into the SQL literal.
    assert "websearch_to_tsquery('english', 'climate')" not in sql
    assert params.get("query") == "climate"


def test_migration_072_rebuilds_search_tsv_on_english():
    """Migration 072 must rebuild search_tsv on a FIXED 'english' config and
    recreate the GIN index the query paths depend on."""
    mig = (
        REPO_ROOT
        / "infrastructure"
        / "database"
        / "migrations"
        / "versions"
        / "072_fts_english_rebuild.sql"
    )
    assert mig.exists(), "migration 072_fts_english_rebuild.sql is missing"
    # Strip line comments — the header prose legitimately names the old
    # clilens_lang_cfg(language_code) build; only the executable SQL matters.
    body = "\n".join(
        line
        for line in mig.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("--")
    ).lower()

    # Rebuilds the generated column with a constant 'english' config.
    assert "drop column if exists search_tsv" in body
    assert "add column search_tsv" in body
    assert "to_tsvector(" in body and "'english'" in body
    # The generated-column expression must NOT be rebuilt on the per-row
    # (mislabelled) config — i.e. no to_tsvector(clilens_lang_cfg(...), …).
    # (The COMMENT prose may still name the function historically.)
    assert "to_tsvector(clilens_lang_cfg" not in body
    # Recreates the GIN index used by every FTS path.
    assert "drop index if exists idx_articles_search_tsv" in body
    assert "create index idx_articles_search_tsv" in body
    # No table creation — it is an in-place rebuild.
    assert "create table" not in body
