-- 0002: widen citations_index.tx_hash to accept a Circle Gateway transfer id (UUID),
-- not only an on-chain Arc tx hash. Batched x402 settles many citation tolls in one
-- on-chain mint and returns a per-toll Gateway transfer UUID synchronously; that UUID
-- is the canonical settlement reference until a recipient withdraws to a 0x hash.
-- Mirrors shared/types.py _TX_HASH.
BEGIN;

ALTER TABLE citations_index DROP CONSTRAINT IF EXISTS citations_index_tx_hash_check;

ALTER TABLE citations_index
    ADD CONSTRAINT citations_index_tx_hash_check
    CHECK (
        tx_hash IS NULL
        OR tx_hash ~ '^(0x[0-9a-fA-F]{64}|[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})$'
    );

COMMIT;
