# Schema v2 — 调区归属版本
Adds time-versioned sensor zone attribution on top of v1.

- `zone_batches`: one row per accepted registration batch; `version` is a per-dataset monotonically increasing integer (current version = max, 0 when none). `actor`/`note`/`created_at` audit the backfill.
- `zone_intervals`: `batch_id` + `dataset_id` + `sensor_id` + `zone` + `valid_from`/`valid_to` (canonical ISO 8601 strings). Intervals are half-open `[valid_from, valid_to)`; per sensor they never overlap — registration locks the dataset row `FOR UPDATE`, validates the whole batch against committed intervals and itself, and rejects the entire batch with 409 on any overlap.
- `traces.zone_version` (added via idempotent `ALTER TABLE ... IF NOT EXISTS`): attribution version pinned at acceptance. The trace snapshot also embeds `zone_version` + `zone_intervals`, so queued/running/completed profiles always resolve the same attribution and archives are never rewritten.

`hash_join` gains optional `zone_mode`: `current` (default, original sensors-table join) or `sample_time` (zone attributed by `recorded_at`; readings outside all intervals are dropped from the join).
