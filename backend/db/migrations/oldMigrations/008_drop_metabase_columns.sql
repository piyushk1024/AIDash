-- Drops Metabase-specific columns from dataset_metadata, retired along
-- with the Metabase container and metabaseClient.py/metabaseRoute.py.
-- metabase_table_id: was Metabase's own table reference, replaced by
--   field_map derived directly from csvLoader's column type inference.
-- metabase_dashboard_id: was the single shared dashboard slot; dashboard
--   state now lives entirely in dashboard_plans.plan_json, scoped by mode.

ALTER TABLE dataset_metadata
DROP COLUMN IF EXISTS metabase_table_id,
DROP COLUMN IF EXISTS metabase_dashboard_id;