"use client";

import { useState } from "react";
import { errorMessage, postJson } from "@/lib/api";
import type { RetroResponse } from "@/lib/capabilities";
import { Card, ErrorNote, Field } from "./Card";

interface Row {
  wallet: string;
  impact: string;
}

const SEED: Row[] = [
  { wallet: "0x" + "a".repeat(40), impact: "40" },
  { wallet: "0x" + "b".repeat(40), impact: "10" },
];

export function RetroPanel() {
  const [pool, setPool] = useState("0.01");
  const [rows, setRows] = useState<Row[]>(SEED);
  const [res, setRes] = useState<RetroResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function setRow(i: number, patch: Partial<Row>) {
    setRows((prev) => prev.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  }

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const body = {
        pool,
        projects: rows.map((r) => ({ wallet: r.wallet, impact: Number(r.impact) })),
      };
      setRes(await postJson<RetroResponse>("/api/retro", body));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="Retroactive funding" subtitle="Reward what proved valuable, by realized impact (PA 07)">
      <Field label="Pool (USDC)">
        <input
          value={pool}
          onChange={(e) => setPool(e.target.value)}
          className="w-32 rounded border border-outline-variant/40 bg-surface-container-lowest text-on-surface placeholder:text-outline px-2 py-1 font-mono"
        />
      </Field>

      <div className="mt-3 space-y-2">
        {rows.map((r, i) => (
          <div key={i} className="flex gap-2">
            <input
              value={r.wallet}
              onChange={(e) => setRow(i, { wallet: e.target.value })}
              className="flex-1 rounded border border-outline-variant/40 bg-surface-container-lowest text-on-surface placeholder:text-outline px-2 py-1 font-mono text-xs"
              placeholder="0x project"
            />
            <input
              value={r.impact}
              onChange={(e) => setRow(i, { impact: e.target.value })}
              className="w-24 rounded border border-outline-variant/40 bg-surface-container-lowest text-on-surface placeholder:text-outline px-2 py-1 font-mono"
              placeholder="impact"
            />
          </div>
        ))}
        <button
          type="button"
          onClick={() => setRows((prev) => [...prev, { wallet: "", impact: "1" }])}
          className="text-sm text-primary-fixed-dim"
        >
          + project
        </button>
      </div>

      <button
        type="button"
        onClick={submit}
        disabled={busy}
        className="mt-4 rounded bg-primary-fixed-dim px-4 py-2 text-on-primary-fixed font-bold disabled:opacity-50"
      >
        {busy ? "Awarding…" : "Award by impact"}
      </button>

      <ErrorNote message={error} />

      {res && (
        <ul className="mt-4 space-y-1 text-sm">
          {res.projects.map((p) => (
            <li key={p.wallet} className="flex items-center justify-between font-mono">
              <span className="truncate">{p.wallet.slice(0, 12)}… · impact {p.impact}</span>
              <span className="text-secondary-fixed-dim">+{p.award}</span>
            </li>
          ))}
          <li className="mt-1 border-t pt-1 text-xs text-on-surface-variant">
            total awarded {res.total_awarded} USDC
          </li>
        </ul>
      )}
    </Card>
  );
}
