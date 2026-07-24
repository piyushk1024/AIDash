-- Adds staleness tracking to dashboard_plans.
---- stale: set to true when upstream semantics are re-run with a changed hint,
--   signalling that the plan was derived from outdated column classifications.
---- generation_counter: incremented on each staleness event. Lets the UI detect
--   drift between what the user sees and what the current semantics would produce.
---- Both default to safe values — existing rows are treated as fresh on migration.

ALTER TABLE dashboard_plans
ADD COLUMN IF NOT EXISTS stale BOOLEAN DEFAULT false,
ADD COLUMN IF NOT EXISTS generation_counter INTEGER DEFAULT 0;