"""Behavioral tests for the Stripe webhook handler (audit TEST-002).

The webhook is the money + signature-verification path and previously had zero
coverage. These tests mock `stripe.Webhook.construct_event` (so the real
signature-rejection branch is exercised without a live secret) and the DB, then
assert the side effects: tier sync on update, freemium revert on cancel, and a
payment_history insert on a paid invoice.
"""

from __future__ import annotations

import asyncio

import pytest
import stripe
from fastapi import HTTPException
from unittest.mock import MagicMock, patch

import api.subscription_routes as subs


class StripeObj(dict):
    """dict that also supports attribute access — mimics the stripe object API
    (events are accessed as both `event.type` and `sub["items"]["data"]`)."""

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError as exc:
            raise AttributeError(key) from exc


class _FakeRequest:
    def __init__(self, body: bytes = b"{}"):
        self._body = body

    async def body(self) -> bytes:
        return self._body


def _run(coro):
    return asyncio.run(coro)


def _sub_event(event_type, *, sub_id="sub_1", status="active", price_id=None,
               period_end=1893456000, user_id="u1"):
    sub = StripeObj(
        id=sub_id,
        status=status,
        current_period_end=period_end,
        metadata=StripeObj(user_id=user_id) if user_id else StripeObj(),
    )
    if price_id is not None:
        sub["items"] = StripeObj(data=[StripeObj(price=StripeObj(id=price_id))])
    return StripeObj(type=event_type, data=StripeObj(object=sub))


def _invoice_event(event_type, *, invoice_id="in_1", customer="cus_1",
                   amount=999, currency="usd"):
    inv = StripeObj(
        id=invoice_id, customer=customer, amount_paid=amount, amount_due=amount,
        currency=currency, description="Subscription payment",
        hosted_invoice_url="https://stripe/inv",
    )
    return StripeObj(type=event_type, data=StripeObj(object=inv))


def _updates(db_mock):
    """All (sql, params) pairs passed to execute_update."""
    out = []
    for call in db_mock.execute_update.call_args_list:
        sql = call.args[0] if call.args else call.kwargs.get("sql", "")
        params = call.kwargs.get("params", call.args[1] if len(call.args) > 1 else {})
        out.append((sql, params))
    return out


class TestSignatureRejection:
    def test_invalid_signature_returns_400(self):
        with patch.object(
            stripe.Webhook, "construct_event",
            side_effect=stripe.error.SignatureVerificationError("bad sig", "sig-header"),
        ):
            with pytest.raises(HTTPException) as ei:
                _run(subs.stripe_webhook(_FakeRequest(), stripe_signature="whatever"))
        assert ei.value.status_code == 400

    def test_malformed_payload_returns_400(self):
        with patch.object(stripe.Webhook, "construct_event", side_effect=ValueError("bad")):
            with pytest.raises(HTTPException) as ei:
                _run(subs.stripe_webhook(_FakeRequest(), stripe_signature="whatever"))
        assert ei.value.status_code == 400


class TestSubscriptionUpdated:
    def test_known_price_syncs_subscription_and_user_tier(self):
        db = MagicMock()
        event = _sub_event("customer.subscription.updated", price_id="price_pro", status="active")
        with patch.object(stripe.Webhook, "construct_event", return_value=event), \
             patch.object(subs, "PRICE_IDS", {"professional": "price_pro"}), \
             patch.object(subs, "get_postgres", return_value=db):
            _run(subs.stripe_webhook(_FakeRequest(), stripe_signature="x"))

        ups = _updates(db)
        # subscriptions row updated to the resolved tier
        assert any("UPDATE subscriptions" in sql and p.get("tier") == "professional"
                   for sql, p in ups), ups
        # the user's tier is synced too
        assert any("UPDATE users" in sql and p.get("tier") == "professional"
                   and p.get("user_id") == "u1" for sql, p in ups), ups


class TestSubscriptionDeleted:
    def test_cancel_marks_canceled_and_reverts_user_to_freemium(self):
        db = MagicMock()
        event = _sub_event("customer.subscription.deleted")
        with patch.object(stripe.Webhook, "construct_event", return_value=event), \
             patch.object(subs, "get_postgres", return_value=db):
            _run(subs.stripe_webhook(_FakeRequest(), stripe_signature="x"))

        ups = _updates(db)
        assert any("UPDATE subscriptions" in sql and "canceled" in sql for sql, _ in ups), ups
        assert any("UPDATE users" in sql and "freemium" in sql and p.get("user_id") == "u1"
                   for sql, p in ups), ups


class TestPaymentSucceeded:
    def test_records_payment_history_when_user_found(self):
        db = MagicMock()
        db.execute_query.return_value = [{"user_id": "u1"}]
        event = _invoice_event("invoice.payment_succeeded", amount=1299)
        with patch.object(stripe.Webhook, "construct_event", return_value=event), \
             patch.object(subs, "get_postgres", return_value=db):
            _run(subs.stripe_webhook(_FakeRequest(), stripe_signature="x"))

        ups = _updates(db)
        assert any("payment_history" in sql and p.get("amount") == 1299
                   and p.get("status") == "succeeded" for sql, p in ups), ups

    def test_no_user_no_payment_row(self):
        db = MagicMock()
        db.execute_query.return_value = []  # no matching user
        event = _invoice_event("invoice.payment_succeeded")
        with patch.object(stripe.Webhook, "construct_event", return_value=event), \
             patch.object(subs, "get_postgres", return_value=db):
            _run(subs.stripe_webhook(_FakeRequest(), stripe_signature="x"))

        assert not any("payment_history" in sql for sql, _ in _updates(db))
