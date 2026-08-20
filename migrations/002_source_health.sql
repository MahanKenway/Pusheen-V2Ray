-- Source health and temporary quarantine state.
-- Registry definitions remain the source of truth; this table records runtime evidence.

CREATE TABLE IF NOT EXISTS source_health (
    source_id TEXT PRIMARY KEY REFERENCES sources(source_id) ON DELETE CASCADE,
    total_runs INTEGER NOT NULL DEFAULT 0 CHECK (total_runs >= 0),
    successful_runs INTEGER NOT NULL DEFAULT 0 CHECK (successful_runs >= 0),
    consecutive_failures INTEGER NOT NULL DEFAULT 0 CHECK (consecutive_failures >= 0),
    last_discovered_count INTEGER NOT NULL DEFAULT 0 CHECK (last_discovered_count >= 0),
    last_accepted_count INTEGER NOT NULL DEFAULT 0 CHECK (last_accepted_count >= 0),
    last_error_code TEXT,
    last_checked_at TIMESTAMPTZ,
    quarantine_until TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS source_health_quarantine_idx
    ON source_health (quarantine_until);
