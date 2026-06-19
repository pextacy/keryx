-- Keryx Neon schema — index / registry / cache ONLY.
-- The chain (Arc) is the canonical settlement ledger. Postgres holds a fast
-- read-index, the author->wallet registry, and a source cache. Never let this
-- become the source of truth for payments (AGENTS.md ground rule #4).
--
-- Apply: psql "$KERYX_DATABASE_URL" -f db/migrations/0001_init.sql

BEGIN;

-- Grounding similarity lives colocated with our Postgres (docs.md).
CREATE EXTENSION IF NOT EXISTS vector;

-- Author -> wallet registry (the moat). One row per payable source author.
CREATE TABLE IF NOT EXISTS authors (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_domain TEXT,
    author_url    TEXT,
    wallet_address TEXT NOT NULL CHECK (wallet_address ~ '^0x[0-9a-fA-F]{40}$'),
    meta          JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT authors_identity UNIQUE (source_domain, author_url)
);

-- Source cache from RSSHub (DataItem.link canonical URL + author).
CREATE TABLE IF NOT EXISTS sources (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    url           TEXT NOT NULL UNIQUE,
    title         TEXT,
    author_ref    BIGINT REFERENCES authors (id) ON DELETE SET NULL,
    content_hash  TEXT,
    raw_dataitem  JSONB,
    -- Embedding of source passages for grounding similarity (pgvector).
    -- 1536 dims is a common default; adjust to the embedding model at M1.
    embedding     VECTOR(1536),
    fetched_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Paying-agent sessions: funded wallet + budget + per-source cap.
CREATE TABLE IF NOT EXISTS sessions (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    agent_wallet   TEXT NOT NULL CHECK (agent_wallet ~ '^0x[0-9a-fA-F]{40}$'),
    budget_total   NUMERIC(20, 6) NOT NULL,
    budget_spent   NUMERIC(20, 6) NOT NULL DEFAULT 0,
    per_source_cap NUMERIC(20, 6),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT budget_nonneg CHECK (budget_spent >= 0 AND budget_total >= budget_spent)
);

-- Mirror of chain for dashboard speed. CHAIN IS CANONICAL — reconcile against it.
CREATE TABLE IF NOT EXISTS citations_index (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    session_id      BIGINT REFERENCES sessions (id) ON DELETE CASCADE,
    source_id       BIGINT REFERENCES sources (id) ON DELETE SET NULL,
    grounding_score DOUBLE PRECISION NOT NULL CHECK (grounding_score BETWEEN 0 AND 1),
    amount          NUMERIC(20, 6) NOT NULL CHECK (amount >= 0),
    tx_hash         TEXT CHECK (tx_hash IS NULL OR tx_hash ~ '^0x[0-9a-fA-F]{64}$'),
    cited           BOOLEAN NOT NULL DEFAULT true,  -- false = evaluated-but-not-cited ($0)
    settled_at      TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_citations_session  ON citations_index (session_id);
CREATE INDEX IF NOT EXISTS idx_citations_tx        ON citations_index (tx_hash);
CREATE INDEX IF NOT EXISTS idx_citations_settled   ON citations_index (settled_at);
CREATE INDEX IF NOT EXISTS idx_sources_author      ON sources (author_ref);

COMMIT;
