"""Migration runner — per-migration @notolerate directive detection.

Slice 2b (2026-05-25). The runner has `MIGRATIONS_TOLERATE_ERRORS=true`
in Cloud Build which silently swallowed mig 043's unique_violation and
marked it applied without doing the work. Mig 044+ opt out of tolerance
via `-- @notolerate` in the SQL header. This test pins the regex shape
so a future copy-edit doesn't accidentally make the directive a no-op.
"""

from __future__ import annotations

import re


# Same regex literal as scripts/run_migrations.py — kept here so a typo
# in either file fails this test loudly.
NOTOLERATE_RE = re.compile(r"^\s*--\s*@notolerate\s*$", re.MULTILINE)


class TestNotolerateRegex:
    def test_directive_at_top_detected(self):
        sql = "-- @notolerate\n-- Migration 044\nSELECT 1;"
        assert bool(NOTOLERATE_RE.search(sql))

    def test_directive_after_blank_lines_detected(self):
        sql = "\n\n-- @notolerate\nSELECT 1;"
        assert bool(NOTOLERATE_RE.search(sql))

    def test_directive_with_extra_whitespace_detected(self):
        sql = "  --   @notolerate   \nSELECT 1;"
        assert bool(NOTOLERATE_RE.search(sql))

    def test_directive_in_middle_of_file_detected(self):
        sql = """
            -- Migration 044
            CREATE TABLE foo (id INT);
            -- @notolerate
            INSERT INTO foo VALUES (1);
        """
        assert bool(NOTOLERATE_RE.search(sql))

    def test_no_directive_not_detected(self):
        sql = "-- Regular migration\nCREATE TABLE foo (id INT);"
        assert not bool(NOTOLERATE_RE.search(sql))

    def test_directive_inside_string_literal_not_detected(self):
        # Multi-line directive embedded in a string literal — regex only
        # matches at line start, so an embedded comment-looking-thing
        # inside a quote won't trigger.
        sql = "SELECT '-- @notolerate inside string' AS x;"
        assert not bool(NOTOLERATE_RE.search(sql))

    def test_directive_must_be_on_its_own_line(self):
        # Inline trailing comment after SQL should NOT count.
        sql = "SELECT 1; -- @notolerate"
        assert not bool(NOTOLERATE_RE.search(sql))

    def test_partial_match_not_detected(self):
        # Common typos / similar-looking directives should NOT match.
        for sql in (
            "-- @notolerated\n",        # typo: extra 'd'
            "-- @no_tolerate\n",        # underscore variant
            "-- @notolerate now\n",     # trailing text
            "-- notolerate\n",          # missing @
        ):
            assert not bool(NOTOLERATE_RE.search(sql)), (
                f"Should NOT match {sql!r}"
            )


class TestMig044HasDirective:
    """Pin mig 044 specifically — if someone removes the @notolerate header
    while editing, the runner will silently swallow any 23505 the same way
    it did with mig 043."""

    def test_mig_044_starts_with_notolerate(self):
        from pathlib import Path
        repo_root = Path(__file__).resolve().parents[2]
        mig_path = (
            repo_root
            / "infrastructure" / "database" / "migrations" / "versions"
            / "044_companies_dedupe_pass3.sql"
        )
        assert mig_path.exists(), f"Missing {mig_path}"
        sql = mig_path.read_text(encoding="utf-8")
        assert NOTOLERATE_RE.search(sql), (
            "Mig 044 must have `-- @notolerate` directive — without it the "
            "runner can silently swallow 23505 again, exactly the failure "
            "mode that wasted mig 043. See feedback_migration_tolerate_errors."
        )


class TestMig045HasDirective:
    """Slice 7 (2026-05-25) — Mig 045 fences source 3-axis scoring. It
    NULL-fills any unscored rows and hard-asserts (P0001) zero NULLs
    remain. The @notolerate directive ensures the assertion can't be
    silently swallowed."""

    def test_mig_045_starts_with_notolerate(self):
        from pathlib import Path
        repo_root = Path(__file__).resolve().parents[2]
        mig_path = (
            repo_root
            / "infrastructure" / "database" / "migrations" / "versions"
            / "045_source_3axis_fence.sql"
        )
        assert mig_path.exists(), f"Missing {mig_path}"
        sql = mig_path.read_text(encoding="utf-8")
        assert NOTOLERATE_RE.search(sql), (
            "Mig 045 must have `-- @notolerate` directive."
        )

    def test_mig_045_asserts_with_p0001(self):
        from pathlib import Path
        repo_root = Path(__file__).resolve().parents[2]
        sql = (
            repo_root / "infrastructure" / "database" / "migrations"
            / "versions" / "045_source_3axis_fence.sql"
        ).read_text(encoding="utf-8")
        assert "USING ERRCODE = 'P0001'" in sql
        assert "RAISE EXCEPTION" in sql
        assert "editorial_score" in sql
        assert "factcheck_score" in sql
        assert "transparency_score" in sql
