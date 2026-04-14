ALTER TABLE dataset_metadata
ADD COLUMN IF NOT EXISTS metabase_dashboard_id INTEGER;
ALTER TABLE dataset_metadata ADD COLUMN IF NOT EXISTS public_url TEXT;