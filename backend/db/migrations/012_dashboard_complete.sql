ALTER TABLE dataset_metadata
    ADD COLUMN dashboard_complete BOOLEAN NOT NULL DEFAULT false;

UPDATE dataset_metadata dm
SET dashboard_complete = true
FROM dashboard_plans dp
WHERE dp.dataset_id = dm.dataset_id
  AND EXISTS (
      SELECT 1 FROM jsonb_array_elements(dp.plan_json->'charts') AS c
      WHERE c ? 'card_id'
  );