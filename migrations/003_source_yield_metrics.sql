CREATE TABLE IF NOT EXISTS source_yield_metrics (
    source_id TEXT NOT NULL REFERENCES sources(source_id) ON DELETE CASCADE,
    protocol TEXT NOT NULL,
    validation_samples INTEGER NOT NULL DEFAULT 0 CHECK (validation_samples >= 0),
    end_to_end_successes INTEGER NOT NULL DEFAULT 0 CHECK (end_to_end_successes >= 0),
    qualified_count INTEGER NOT NULL DEFAULT 0 CHECK (qualified_count >= 0),
    last_observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (source_id, protocol)
);

CREATE INDEX IF NOT EXISTS source_yield_metrics_source_idx
    ON source_yield_metrics (source_id, validation_samples DESC, last_observed_at DESC);
