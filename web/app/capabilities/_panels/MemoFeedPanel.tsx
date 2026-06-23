"use client";

import { useState } from "react";
import { errorMessage, getJson } from "@/lib/api";
import { ARC_EXPLORER_TX } from "@/lib/types";
import type { MemoThreadResponse, MemosResponse } from "@/lib/capabilities";
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
  "authorization",
  "note",
] as const;

const KIND_COLOR: Record<string, string> = {
  citation: "bg-primary-fixed-dim/20 text-primary-fixed-dim",
  swap: "bg-emerald-100 text-emerald-700",
  refund: "bg-tertiary-fixed-dim/20 text-tertiary-fixed-dim",
  payout: "bg-error-container/20 text-error",
  royalty: "bg-pink-100 text-pink-700",
  job: "bg-indigo-100 text-indigo-700",
  invoice: "bg-teal-100 text-teal-700",
  attestation: "bg-cyan-100 text-cyan-700",
  authorization: "bg-orange-100 text-orange-700",
};

function kindColor(kind?: string): string {
  return (kind && KIND_COLOR[kind]) || "bg-white/5 text-on-surface-variant";
}

export function MemoFeedPanel() {
  const [kind, setKind] = useState<(typeof KINDS)[number]>("");
  const [data, setData] = useState<MemosResponse | null>(null);
  const [thread, setThread] = useState<MemoThreadResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    setBusy(true);
    setError(null);
    setThread(null);
    try {
      const q = kind ? `?kind=${encodeURIComponent(kind)}&limit=15` : "?limit=15";
      setData(await getJson<MemosResponse>(`/api/memos${q}`));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function loadThread(tx: string) {
    setError(null);
    try {
      const t = await getJson<MemoThreadResponse>(`/api/memo/${encodeURIComponent(tx)}/thread`);
      setThread(t.tx_hash === thread?.tx_hash ? null : t); // toggle
    } catch (err) {
      setError(errorMessage(err));
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
            className="rounded border border-outline-variant/40 bg-surface-container-lowest text-on-surface placeholder:text-outline px-2 py-1 text-sm"
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
        <p className="mt-3 text-xs text-on-surface-variant">no memos yet — send a payment or run the demo</p>
      )}

      {data && data.count > 0 && (
        <ul className="mt-4 space-y-2">
          {data.memos.map((m) => (
            <li key={m.tx_hash} className="rounded border border-white/5 bg-white/5 p-2 text-sm">
              <div className="flex items-center gap-2">
                <span
                  className={`rounded px-1.5 py-0.5 text-[11px] font-medium ${kindColor(m.meta?.kind)}`}
                >
                  {m.meta?.kind ?? "note"}
                </span>
                {m.meta?.scheme === "confidential" && (
                  <span
                    title="confidential — note redacted in this feed (recibo encrypted scheme)"
                    className="rounded bg-surface-container-high px-1.5 py-0.5 text-[11px] font-medium text-white"
                  >
                    🔒
                  </span>
                )}
                <a
                  href={ARC_EXPLORER_TX + m.tx_hash}
                  target="_blank"
                  className="font-mono text-xs text-primary-fixed-dim underline"
                >
                  {m.tx_hash.slice(0, 12)}…
                </a>
                <Copy text={m.tx_hash} />
                {m.meta?.in_reply_to && (
                  <span title="replies to a prior memo" className="text-[11px] text-outline">
                    ↩ reply
                  </span>
                )}
                <button
                  type="button"
                  onClick={() => void loadThread(m.tx_hash)}
                  className="text-[11px] text-outline hover:text-on-surface"
                >
                  thread
                </button>
              </div>
              {m.meta?.ref && (
                <div className="mt-1 truncate font-mono text-xs text-on-surface-variant" title={m.meta.ref}>
                  ref: {m.meta.ref}
                </div>
              )}
              {m.meta?.note && <div className="mt-0.5 text-xs text-on-surface">{m.meta.note}</div>}
              {m.meta?.attachment_url && (
                <a
                  href={m.meta.attachment_url}
                  target="_blank"
                  className="mt-0.5 inline-block text-xs text-primary-fixed-dim underline"
                >
                  📎 attachment ({m.meta.mime?.split(";")[0] ?? "file"})
                </a>
              )}
              {thread?.tx_hash === m.tx_hash && (
                <div className="mt-2 space-y-1 border-l-2 border-white/10 pl-2 text-xs">
                  {thread.ancestors && thread.ancestors.length > 0 && (
                    <div className="text-on-surface-variant">
                      ↑ replies to:{" "}
                      {thread.ancestors
                        .map((a) => a.meta?.note || a.tx_hash.slice(0, 10))
                        .join(" → ")}
                    </div>
                  )}
                  {thread.replies && thread.replies.length > 0 ? (
                    thread.replies.map((r) => (
                      <div key={r.tx_hash} className="text-on-surface-variant">
                        ↳ {r.meta?.note || r.tx_hash.slice(0, 10)}
                      </div>
                    ))
                  ) : (
                    <div className="text-outline">no replies</div>
                  )}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      <ErrorNote message={error} />
    </Card>
  );
}
