"""Neon-backed settlement ledger — a Postgres mirror of agent/ledger.py's in-memory
``Ledger``, behind the same ``record``/``metrics``/``recent`` surface main.py uses.

CHAIN IS CANONICAL (AGENTS.md #4): this mirrors chain for dashboard read-speed and is
reconciled against it. Active only when ``KERYX_DATABASE_URL`` is set; the in-memory
``Ledger`` stays the offline default. Records the same rows the in-memory ledger does —
only settled (cited, with a tx hash) citations; $0 skips are not ledgered.

Requires migration 0003 (citations_index mirror columns). All SQL is parameterized.
"""

from __future__ import annotations

from decimal import Decimal

from registry.pg import ConnectFn
from shared.types import CitationRecord

_INSERT = """
INSERT INTO citations_index
    (query_hash, agent_wallet, source_url, author_wallet, grounding_score,
     amount, tx_hash, cited, external, settled_at, ts)
VALUES (%s, %s, %s, %s, %s, %s, %s, true, %s, now(), now())
"""

_METRICS = """
SELECT
    COALESCE(SUM(amount), 0)::text                                          AS total,
    COUNT(*)                                                                AS citations,
    COUNT(DISTINCT author_wallet) FILTER (WHERE author_wallet IS NOT NULL)  AS authors,
    COUNT(DISTINCT agent_wallet)                                            AS sessions,
    COUNT(*) FILTER (WHERE external)                                        AS ext_cit,
    COALESCE(SUM(amount) FILTER (WHERE external), 0)::text                  AS ext_total,
    COUNT(*) FILTER (WHERE NOT external)                                    AS team_cit,
    COALESCE(SUM(amount) FILTER (WHERE NOT external), 0)::text              AS team_total
FROM citations_index
WHERE tx_hash IS NOT NULL
"""

_RECENT = """
SELECT source_url, author_wallet, grounding_score, amount::text, tx_hash, external,
       EXTRACT(EPOCH FROM ts)::bigint AS ts
FROM citations_index
WHERE tx_hash IS NOT NULL
ORDER BY ts DESC
LIMIT %s
"""


class PgLedger:
    """Postgres mirror of the settlement ledger (citations_index)."""

    def __init__(self, connect: ConnectFn) -> None:
        self._connect = connect

    def record(
        self,
        *,
        query_hash: str,
        agent_wallet: str,
        citations: list[CitationRecord],
        author_wallets: dict[str, str | None],
        external: bool,
    ) -> None:
        rows = [
            [
                query_hash,
                agent_wallet,
                c.source_url,
                author_wallets.get(c.source_url),
                c.g,
                c.amount,
                c.tx_hash,
                external,
            ]
            for c in citations
            if c.cited and c.tx_hash
        ]
        if not rows:
            return
        with self._connect() as conn, conn.cursor() as cur:
            for params in rows:
                cur.execute(_INSERT, params)

    def metrics(self) -> dict[str, object]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(_METRICS)
            row = cur.fetchone()
        total, cit, authors, sessions, ext_cit, ext_total, team_cit, team_total = (
            row if row is not None else ("0", 0, 0, 0, 0, "0", 0, "0")
        )
        cit = int(cit)
        ext_cit = int(ext_cit)
        return {
            "total_settled_usdc": _norm(total),
            "citations_settled": cit,
            "distinct_author_wallets": int(authors),
            "distinct_sessions": int(sessions),
            "team": {"citations": int(team_cit), "settled_usdc": _norm(team_total)},
            "external": {"citations": ext_cit, "settled_usdc": _norm(ext_total)},
            "external_share_pct": round(100 * ext_cit / cit, 1) if cit else 0.0,
        }

    def recent(self, limit: int = 50) -> list[dict[str, object]]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(_RECENT, [limit])
            rows = cur.fetchall()
        return [
            {
                "source_url": r[0],
                "author_wallet": r[1],
                "g": float(r[2]),
                "amount": _norm(r[3]),
                "tx_hash": r[4],
                "external": bool(r[5]),
                "ts": int(r[6]),
            }
            for r in rows
        ]


def _norm(amount: object) -> str:
    """Normalize a NUMERIC ::text (or Decimal) to the same string form the in-memory ledger
    emits (``str(Decimal)``)."""
    return str(Decimal(str(amount)))
