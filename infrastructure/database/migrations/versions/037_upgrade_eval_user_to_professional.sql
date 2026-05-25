-- Migration 037: Upgrade eval user to Professional tier
--
-- Lets eljailari.suhonen@gmail.com see every paid feature for evaluation.
-- Idempotent: re-running is a no-op (already-Professional users stay
-- Professional). Removed for non-target users.

UPDATE users
SET subscription_tier = 'professional'
WHERE email = 'eljailari.suhonen@gmail.com'
  AND (subscription_tier IS NULL OR subscription_tier != 'professional');

DO $$
DECLARE
    n_upgraded INTEGER;
    target_tier VARCHAR(20);
BEGIN
    SELECT subscription_tier INTO target_tier
    FROM users
    WHERE email = 'eljailari.suhonen@gmail.com'
    LIMIT 1;

    IF target_tier IS NULL THEN
        RAISE NOTICE 'Migration 037: target user not found (sign up first)';
    ELSE
        RAISE NOTICE 'Migration 037: target user tier = %', target_tier;
    END IF;
END
$$;
