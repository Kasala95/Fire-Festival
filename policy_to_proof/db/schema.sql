-- Run-history schema. One row per harness run.
-- record_json holds the full persisted record (same shape as runs/<id>.json);
-- the flat columns are denormalized for fast listing/filtering in the dashboard.
CREATE TABLE IF NOT EXISTS runs (
    run_id      TEXT PRIMARY KEY,
    created_at  REAL    NOT NULL,
    requirement TEXT,
    target      TEXT,
    worker      TEXT,
    decision    TEXT,
    risk_score  INTEGER,
    halted      INTEGER NOT NULL DEFAULT 0,
    escalated   INTEGER NOT NULL DEFAULT 0,
    record_json TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_runs_created_at ON runs (created_at DESC);
