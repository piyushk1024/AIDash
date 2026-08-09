-- 010_llm_quota_fix.sql
-- Switches daily_llm_usage from one-row-per-user-per-day to one-row-per-user
-- (usage_date becomes a mutable "last reset date" instead of part of the key),
-- and aligns quota resets with Gemini's actual PT-based RPD reset.

-- Consolidate any existing multi-day rows down to one row per user,
-- keeping only the most recent usage_date (older rows are stale anyway
-- since quota already conceptually reset on those past days).
DELETE FROM daily_llm_usage a
    USING daily_llm_usage b
    WHERE a.user_id = b.user_id
      AND a.usage_date < b.usage_date;

ALTER TABLE daily_llm_usage
    DROP CONSTRAINT daily_llm_usage_pkey;

ALTER TABLE daily_llm_usage
    ADD PRIMARY KEY (user_id);