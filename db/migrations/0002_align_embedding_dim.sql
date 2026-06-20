-- Keryx migration 0002 — align the source-embedding dimension to the active model,
-- and add a clean author-URL unique index for the registry's author->wallet upsert.
--
-- 0001 declared sources.embedding as VECTOR(1536) with a "adjust to the model" note.
-- The default dense embedder (voyage-3.5, see shared/config.py KERYX_EMBEDDING_MODEL) emits
-- 1024-dim vectors. Embeddings are an OPTIONAL similarity cache (chain stays canonical and
-- the BagOfWords path needs no DB), so dropping/recreating the column is non-destructive.
--
-- Apply: psql "$KERYX_DATABASE_URL" -f db/migrations/0002_align_embedding_dim.sql

BEGIN;

-- Re-create the embedding column at the model's dimension. Keep VECTOR so pgvector's
-- cosine operator (<=>) works. If you switch models, re-run with the new dimension.
ALTER TABLE sources DROP COLUMN IF EXISTS embedding;
ALTER TABLE sources ADD COLUMN embedding VECTOR(1024);

-- Approximate-NN index for cosine nearest-source retrieval (pgvector). ivfflat needs an
-- ANALYZE / populated table to be effective; harmless to create empty.
CREATE INDEX IF NOT EXISTS idx_sources_embedding
    ON sources USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- The registry maps a single author string -> wallet. 0001's UNIQUE (source_domain,
-- author_url) treats NULL source_domain as distinct, so ON CONFLICT can't upsert by author
-- alone. A plain unique index on author_url gives the registry a clean upsert target.
CREATE UNIQUE INDEX IF NOT EXISTS authors_author_url_key ON authors (author_url);

COMMIT;
