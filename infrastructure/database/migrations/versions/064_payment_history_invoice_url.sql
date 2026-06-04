-- Migration 064: payment_history.invoice_url (Stripe hosted invoice link)
--
-- subscription_routes.py has always SELECTed/INSERTed an `invoice_url` column on
-- payment_history (the Stripe `hosted_invoice_url`, surfaced by the /api/subscription
-- /history endpoint and PaymentHistoryItem.invoice_url), but the column was never
-- in the schema (03_users_and_subscriptions.sql / apply_user_tables.sql). The same
-- commit that fixes the broader subscriptions/payment column-name drift relies on
-- this column existing, so add it here.
--
-- Additive + nullable + IF NOT EXISTS => bulletproof, one transaction (see
-- run_migrations.py). No backfill: historical rows simply have a NULL invoice link.

ALTER TABLE payment_history
    ADD COLUMN IF NOT EXISTS invoice_url TEXT;
