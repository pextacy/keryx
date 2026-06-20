-- Keryx migration 0003 — extend citations_index into a full mirror of the settlement
-- ledger (agent/ledger.py LedgerEntry), so the Pg-backed PgLedger records and serves the
-- same rows/metrics as the in-memory Ledger.
--
-- CHAIN IS CANONICAL (AGENTS.md #4). citations_index is a fast read-index/mirror only —
-- reconcile it against chain; never treat it as the source of truth for payments.
--
-- Apply: psql "$KERYX_DATABASE_URL" -f db/migrations/0003_citations_mirror.sql

BEGIN;

ALTER TABLE citations_index
    ADD COLUMN IF NOT EXISTS query_hash    TEXT,
    ADD COLUMN IF NOT EXISTS agent_wallet  TEXT,
    ADD COLUMN IF NOT EXISTS source_url    TEXT,
    ADD COLUMN IF NOT EXISTS author_wallet TEXT,
    ADD COLUMN IF NOT EXISTS external      BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS ts            TIMESTAMPTZ NOT NULL DEFAULT now();

CREATE INDEX IF NOT EXISTS idx_citations_agent ON citations_index (agent_wallet);
CREATE INDEX IF NOT EXISTS idx_citations_author ON citations_index (author_wallet);
CREATE INDEX IF NOT EXISTS idx_citations_ts_desc ON citations_index (ts DESC);

COMMIT;
