"""Schema-alignment regression guard for the subscription / payment routes.

Root cause this pins (audit seq-12 prereq): subscription_routes.py drifted from
the `subscriptions` / `payment_history` DDL — it queried `id`, `subscription_tier`,
`subscription_status`, `subscription_start_date`, `subscription_end_date`,
`canceled_at`, `amount` while the schema defines `subscription_id`, `tier`,
`status`, `current_period_start`, `current_period_end`, `cancelled_at`,
`amount_cents`. Every create/upgrade/cancel therefore 500'd and /history silently
returned []. There is no ORM and CI has no live Postgres, so column drift only
surfaced as a prod 500. This test parses the canonical DDL and asserts the
contract without needing a database.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DDL = REPO_ROOT / "infrastructure" / "database" / "03_users_and_subscriptions.sql"
ROUTE = REPO_ROOT / "api" / "subscription_routes.py"

# Column-list / constraint keywords that start a line inside a CREATE TABLE block
# but are NOT a column definition.
_NON_COLUMN = {
    "primary", "foreign", "unique", "check", "constraint", "create", "--",
}


def _columns_of(table: str) -> set[str]:
    """Extract the column identifiers of a CREATE TABLE block from the DDL."""
    sql = DDL.read_text(encoding="utf-8")
    m = re.search(
        rf"CREATE TABLE IF NOT EXISTS {table}\s*\((.*?)\n\);",
        sql,
        re.IGNORECASE | re.DOTALL,
    )
    assert m, f"could not locate CREATE TABLE for {table} in {DDL}"
    cols: set[str] = set()
    for raw in m.group(1).splitlines():
        line = raw.strip()
        if not line or line.startswith("--"):
            continue
        first = line.split()[0].lower()
        if first in _NON_COLUMN:
            continue
        if re.fullmatch(r"[a-z_][a-z0-9_]*", first):
            cols.add(first)
    return cols


# Columns the route's SQL depends on, per table. If the DDL renames or drops one,
# the corresponding query 500s — so these must always be a subset of the schema.
SUBSCRIPTIONS_REQUIRED = {
    "subscription_id", "user_id", "tier", "status",
    "stripe_customer_id", "stripe_subscription_id", "stripe_price_id",
    "current_period_start", "current_period_end",
    "cancel_at_period_end", "cancelled_at", "created_at", "updated_at",
}
PAYMENT_HISTORY_REQUIRED = {
    "payment_id", "user_id", "stripe_invoice_id", "amount_cents",
    "currency", "status", "description", "invoice_url", "created_at",
}

# Names that only ever referred to non-existent subscription-table columns. They
# are unambiguous (unlike `subscription_tier`, which is a real users-table column),
# so their reappearance in the route is always the drift bug regressing.
FORBIDDEN_IN_ROUTE = (
    "subscription_status",
    "subscription_start_date",
    "subscription_end_date",
    "canceled_at",  # American spelling; the column is `cancelled_at`
)


def test_subscriptions_required_columns_exist_in_ddl():
    cols = _columns_of("subscriptions")
    missing = SUBSCRIPTIONS_REQUIRED - cols
    assert not missing, f"subscriptions DDL missing columns the route uses: {sorted(missing)}"


def test_payment_history_required_columns_exist_in_ddl():
    cols = _columns_of("payment_history")
    missing = PAYMENT_HISTORY_REQUIRED - cols
    assert not missing, f"payment_history DDL missing columns the route uses: {sorted(missing)}"


@pytest.mark.parametrize("token", FORBIDDEN_IN_ROUTE)
def test_route_does_not_reference_legacy_column_names(token):
    src = ROUTE.read_text(encoding="utf-8")
    assert token not in src, (
        f"subscription_routes.py references legacy column '{token}' which does not "
        f"exist in the subscriptions schema — this is the seq-12 drift bug regressing."
    )
