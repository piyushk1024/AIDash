-- Replaces the Metabase-era public_url (an iframe embed link) with a
-- mode marker: which dashboard (pipeline or agent) is currently published.
-- The public endpoint now serves that mode's built charts directly rather
-- than embedding an external link. public_url dropped as unused.

ALTER TABLE dataset_metadata
DROP COLUMN IF EXISTS public_url,
ADD COLUMN IF NOT EXISTS published_mode TEXT;