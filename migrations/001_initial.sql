-- Kaveh PostgreSQL schema v1
-- Raw URIs contain credentials. Database access, backups, and logs must be protected.

CREATE TABLE IF NOT EXISTS kaveh_schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sources (
    source_id TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    trust_weight REAL NOT NULL CHECK (trust_weight >= 0 AND trust_weight <= 1),
    allowed_protocols JSONB NOT NULL DEFAULT '[]'::jsonb,
    max_bytes INTEGER NOT NULL CHECK (max_bytes > 0),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS configs (
    identity_hash CHAR(64) PRIMARY KEY,
    protocol TEXT NOT NULL,
    host TEXT NOT NULL,
    port INTEGER NOT NULL CHECK (port BETWEEN 1 AND 65535),
    credential TEXT NOT NULL,
    transport JSONB NOT NULL,
    label TEXT,
    raw_uri TEXT NOT NULL,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS config_observations (
    identity_hash CHAR(64) NOT NULL REFERENCES configs(identity_hash) ON DELETE CASCADE,
    source_id TEXT NOT NULL REFERENCES sources(source_id) ON DELETE CASCADE,
    raw_hash CHAR(64) NOT NULL,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (identity_hash, source_id)
);

CREATE TABLE IF NOT EXISTS validation_runs (
    run_id UUID PRIMARY KEY,
    policy_version TEXT NOT NULL,
    vantage_id TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed')),
    error_code TEXT
);

CREATE TABLE IF NOT EXISTS probe_results (
    result_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id UUID REFERENCES validation_runs(run_id) ON DELETE SET NULL,
    identity_hash CHAR(64) NOT NULL REFERENCES configs(identity_hash) ON DELETE CASCADE,
    stage TEXT NOT NULL,
    outcome TEXT NOT NULL CHECK (outcome IN ('pass', 'fail', 'skipped')),
    latency_ms INTEGER CHECK (latency_ms IS NULL OR latency_ms >= 0),
    error_code TEXT,
    vantage_id TEXT NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS config_status (
    identity_hash CHAR(64) PRIMARY KEY REFERENCES configs(identity_hash) ON DELETE CASCADE,
    state TEXT NOT NULL,
    last_stage TEXT,
    last_outcome TEXT,
    last_error_code TEXT,
    last_checked_at TIMESTAMPTZ,
    last_e2e_success_at TIMESTAMPTZ,
    score INTEGER CHECK (score IS NULL OR score BETWEEN 0 AND 100),
    policy_version TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS scorecards (
    identity_hash CHAR(64) NOT NULL REFERENCES configs(identity_hash) ON DELETE CASCADE,
    policy_version TEXT NOT NULL,
    score INTEGER NOT NULL CHECK (score BETWEEN 0 AND 100),
    qualified BOOLEAN NOT NULL,
    explanation JSONB NOT NULL,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (identity_hash, policy_version, computed_at)
);

CREATE TABLE IF NOT EXISTS publication_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    policy_version TEXT NOT NULL,
    config_count INTEGER NOT NULL CHECK (config_count >= 0),
    artifact_hash CHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    is_latest BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS probe_results_identity_observed_idx
    ON probe_results (identity_hash, observed_at DESC);
CREATE INDEX IF NOT EXISTS probe_results_stage_outcome_idx
    ON probe_results (stage, outcome, observed_at DESC);
CREATE INDEX IF NOT EXISTS config_status_checked_idx
    ON config_status (last_checked_at NULLS FIRST);
CREATE INDEX IF NOT EXISTS config_observations_source_idx
    ON config_observations (source_id, last_seen_at DESC);
