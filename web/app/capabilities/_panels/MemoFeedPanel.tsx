"use client";

import { useState } from "react";
import { errorMessage, getJson } from "@/lib/api";
import { ARC_EXPLORER_TX } from "@/lib/types";
import type { MemosResponse } from "@/lib/capabilities";
import { Copy } from "@/app/Copy";
import { Card, ErrorNote, Field } from "./Card";

// Recibo-style receipt feed: every settlement carries a structured memo (kind/ref/note +
// metadata + from->to routing). This reads GET /memos and renders each as a receipt,
// filterable by kind — the legible "why was this paid" trail.
const KINDS = [
  "",
  "citation",
  "swap",
  "refund",
  "payout",
  "royalty",
  "job",
  "invoice",
  "attestation",
  "note",
] as const;

const KIND_COLOR: Record<string, string> = {
  citation: "bg-blue-100 text-blue-700",
  swap: "bg-emerald-100 text-emerald-700",
  refund: "bg-purple-100 text-purple-700",
  payout: "bg-amber-100 text-amber-700",
  royalty: "bg-pink-100 text-pink-700",
  job: "bg-indigo-100 text-indigo-700",
  invoice: "bg-teal-100 text-teal-700",
  attestation: "bg-cyan-100 text-cyan-700",
};

function kindColor(kind?: string): string {
  return (kind && KIND_COLOR[kind]) || "bg-gray-100 text-gray-600";
}

export function MemoFeedPanel() {
  const [kind, setKind] = useState<(typeof KINDS)[number]>("");
  const [data, setData] = useState<MemosResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    setBusy(true);
    setError(null);
    try {
      const q = kind ? `?kind=${encodeURIComponent(kind)}&limit=15` : "?limit=15";
      setData(await getJson<MemosResponse>(`/api/memos${q}`));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card
      title="Receipt feed (recibo)"
      subtitle="Structured provenance memos — why each payment was made (kind · ref · note)"
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
          disabled={busy}
          className="mb-1 rounded border px-3 py-1.5 text-sm disabled:opacity-50"
        >
          {busy ? "Loading…" : "Load feed"}
        </button>
      </div>

      {data && data.count === 0 && (
        <p className="mt-3 text-xs text-gray-500">no memos yet — send a payment or run the demo</p>
      )}

      {data && data.count > 0 && (
        <ul className="mt-4 space-y-2">
          {data.memos.map((m) => (
            <li key={m.tx_hash} className="rounded border border-gray-100 bg-gray-50 p-2 text-sm">
              <div className="flex items-center gap-2">
                <span
                  className={`rounded px-1.5 py-0.5 text-[11px] font-medium ${kindColor(m.meta?.kind)}`}
                >
                  {m.meta?.kind ?? "note"}
                </span>
                <a
                  href={ARC_EXPLORER_TX + m.tx_hash}
                  target="_blank"
                  className="font-mono text-xs text-blue-600 underline"
                >
                  {m.tx_hash.slice(0, 12)}…
                </a>
                <Copy text={m.tx_hash} />
              </div>
              {m.meta?.ref && (
                <div className="mt-1 truncate font-mono text-xs text-gray-600" title={m.meta.ref}>
                  ref: {m.meta.ref}
                </div>
              )}
              {m.meta?.note && <div className="mt-0.5 text-xs text-gray-700">{m.meta.note}</div>}
            </li>
          ))}
        </ul>
      )}

      <ErrorNote message={error} />
    </Card>
  );
}
