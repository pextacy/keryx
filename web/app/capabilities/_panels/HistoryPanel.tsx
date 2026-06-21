"use client";

import { useCallback, useEffect, useState } from "react";
import { errorMessage, getJson } from "@/lib/api";
import type { HistoryResponse } from "@/lib/capabilities";
import { Card, ErrorNote, Field } from "./Card";
import { TxLink } from "./TxLink";

const KINDS = [
  "",
  "payout",
  "royalty",
  "qf",
  "retro",
  "bond",
  "stream",
  "send",
  "swap",
  "request",
  "topup",
  "workflow",
  "deposit",
  "gateway_spend",
  "escrow",
  "refund",
] as const;

// Unified settlement feed (GET /history): the raw stream of settlements across every
// primitive, most recent first, optionally filtered by kind. Distinct from the receipt feed
// (provenance memos) — this is every payment that cleared the rail.
export function HistoryPanel() {
  const [kind, setKind] = useState<(typeof KINDS)[number]>("");
  const [data, setData] = useState<HistoryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const q = kind ? `?kind=${encodeURIComponent(kind)}&limit=25` : "?limit=25";
      setData(await getJson<HistoryResponse>(`/api/history${q}`));
    } catch (err) {
      setError(errorMessage(err));
    }
  }, [kind]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <Card
      title="Settlement history"
      subtitle="Every payment that cleared the rail, most recent first"
    >
      <div className="flex items-end gap-2">
        <Field label="Filter by kind">
          <select
            value={kind}
            onChange={(e) => setKind(e.target.value as (typeof KINDS)[number])}
            className="rounded border border-gray-300 px-2 py-1 text-sm"
          >
            {KINDS.map((k) => (
              <option key={k || "all"} value={k}>
                {k || "all"}
              </option>
            ))}
          </select>
        </Field>
        <button
          type="button"
          onClick={() => void load()}
          className="mb-1 rounded border px-3 py-1.5 text-sm"
        >
          Refresh
        </button>
      </div>

      {data && data.count === 0 && (
        <p className="mt-3 text-xs text-gray-500">no settlements yet — use a panel or run the demo</p>
      )}

      {data && data.by_kind && data.by_kind.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {data.by_kind.map((b) => (
            <span
              key={b.kind}
              title={`${b.volume_usdc} USDC`}
              className="rounded bg-gray-100 px-2 py-0.5 text-[11px] text-gray-600"
            >
              {b.kind} <span className="font-semibold text-gray-800">{b.count}</span>
            </span>
          ))}
        </div>
      )}

      {data && data.count > 0 && (
        <ul className="mt-3 divide-y divide-gray-100 text-sm">
          {data.settlements.map((s) => (
            <li key={s.seq} className="flex items-center justify-between gap-2 py-1.5">
              <span className="flex items-center gap-2">
                <span className="rounded bg-gray-100 px-1.5 py-0.5 text-[11px] text-gray-600">
                  {s.kind}
                </span>
                <span className="font-mono text-xs text-gray-400">{s.wallet.slice(0, 10)}…</span>
              </span>
              <span className="flex items-center gap-2 font-mono text-xs">
                <span className="text-green-700">{s.amount}</span>
                {s.tx_hash && <TxLink hash={s.tx_hash} prefix="tx" chars={0} />}
              </span>
            </li>
          ))}
        </ul>
      )}

      <ErrorNote message={error} />
    </Card>
  );
}
