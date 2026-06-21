"use client";

import { useState } from "react";
import { errorMessage, postJson } from "@/lib/api";
import type { EscrowResponse } from "@/lib/capabilities";
import { useToast } from "@/app/Toast";
import { Card, ErrorNote, Field } from "./Card";
import { TxLink } from "./TxLink";

type MilestoneRow = { label: string; amount: string };

// Milestone escrow (ported from arc-escrow): lock a total split across tranches, release each
// to the provider on approval. Shows released vs locked and per-milestone status.
export function EscrowPanel() {
  const { toast, notify } = useToast();
  const [client, setClient] = useState("0x" + "a".repeat(40));
  const [provider, setProvider] = useState("0x" + "b".repeat(40));
  const [rows, setRows] = useState<MilestoneRow[]>([
    { label: "draft", amount: "0.01" },
    { label: "final", amount: "0.02" },
  ]);
  const [esc, setEsc] = useState<EscrowResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const locked = esc !== null;

  function update(i: number, patch: Partial<MilestoneRow>) {
    setRows((rs) => rs.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  }
  function addRow() {
    setRows((rs) => [...rs, { label: "milestone", amount: "0.01" }]);
  }

  async function create() {
    setBusy(true);
    setError(null);
    try {
      const r = await postJson<EscrowResponse>("/api/escrow", {
        client,
        provider,
        milestones: rows.map((m) => ({ label: m.label, amount: m.amount })),
      });
      if (r.error) setError(r.error);
      else setEsc(r);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function release(index: number) {
    if (!esc) return;
    setError(null);
    try {
      const r = await postJson<EscrowResponse>(`/api/escrow/${esc.id}/release`, { index });
      if (r.error) setError(r.error);
      else {
        setEsc(r);
        if (r.tx_hash) notify("Milestone released", r.tx_hash);
      }
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <Card
      title="Milestone escrow (arc-escrow)"
      subtitle="Lock a total split across tranches; release each to the provider on approval"
    >
      {!locked ? (
        <>
          <div className="flex gap-2">
            <Field label="Client (funds)">
              <input
                value={client}
                onChange={(e) => setClient(e.target.value)}
                className="w-full rounded border border-gray-300 px-2 py-1 font-mono text-xs"
              />
            </Field>
            <Field label="Provider (paid)">
              <input
                value={provider}
                onChange={(e) => setProvider(e.target.value)}
                className="w-full rounded border border-gray-300 px-2 py-1 font-mono text-xs"
              />
            </Field>
          </div>
          <div className="mt-3 space-y-2">
            {rows.map((r, i) => (
              <div key={i} className="flex items-center gap-2">
                <input
                  value={r.label}
                  onChange={(e) => update(i, { label: e.target.value })}
                  className="flex-1 rounded border border-gray-300 px-2 py-1 text-sm"
                />
                <input
                  value={r.amount}
                  onChange={(e) => update(i, { amount: e.target.value })}
                  className="w-20 rounded border border-gray-300 px-2 py-1 font-mono text-xs"
                />
              </div>
            ))}
          </div>
          <div className="mt-3 flex gap-2">
            <button type="button" onClick={addRow} className="rounded border px-3 py-1.5 text-sm">
              + Milestone
            </button>
            <button
              type="button"
              onClick={() => void create()}
              disabled={busy}
              className="rounded bg-black px-3 py-1.5 text-sm text-white disabled:opacity-50"
            >
              {busy ? "…" : "Open escrow"}
            </button>
          </div>
        </>
      ) : (
        <>
          <div className="flex items-center justify-between text-sm">
            <span className="font-mono text-gray-500">{esc.id}</span>
            <span
              className={`rounded px-2 py-0.5 text-xs font-medium ${
                esc.status === "completed"
                  ? "bg-green-100 text-green-700"
                  : "bg-amber-100 text-amber-700"
              }`}
            >
              {esc.status}
            </span>
          </div>
          <div className="mt-1 text-xs text-gray-500">
            locked {esc.locked} of {esc.total} USDC
          </div>

          <ul className="mt-3 space-y-2">
            {esc.milestones?.map((m, i) => (
              <li key={i} className="flex items-center justify-between gap-2 text-sm">
                <span className="truncate">{m.label}</span>
                <span className="flex items-center gap-2 font-mono text-xs">
                  <span className="text-green-700">{m.amount}</span>
                  {m.status === "released" ? (
                    m.tx_hash ? (
                      <TxLink hash={m.tx_hash} prefix="released" />
                    ) : (
                      <span className="text-green-600">released ✓</span>
                    )
                  ) : (
                    <button
                      type="button"
                      onClick={() => void release(i)}
                      className="rounded border border-gray-300 px-2 py-0.5 text-gray-700 hover:bg-gray-50"
                    >
                      Release
                    </button>
                  )}
                </span>
              </li>
            ))}
          </ul>

          <button
            type="button"
            onClick={() => {
              setEsc(null);
              setError(null);
            }}
            className="mt-4 rounded border px-3 py-1.5 text-sm"
          >
            New escrow
          </button>
        </>
      )}

      <ErrorNote message={error} />
      {toast}
    </Card>
  );
}
