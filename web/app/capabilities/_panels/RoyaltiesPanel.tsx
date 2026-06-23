"use client";

import { useState } from "react";
import { errorMessage, postJson } from "@/lib/api";
import type { RoyaltiesResponse } from "@/lib/capabilities";
import { Card, ErrorNote, Field } from "./Card";

interface Play {
  wallet: string;
  count: string;
}

const SEED: Play[] = [
  { wallet: "0x" + "a".repeat(40), count: "30" },
  { wallet: "0x" + "b".repeat(40), count: "10" },
  { wallet: "0x" + "c".repeat(40), count: "0" },
];

export function RoyaltiesPanel() {
  const [budget, setBudget] = useState("0.01");
  const [plays, setPlays] = useState<Play[]>(SEED);
  const [res, setRes] = useState<RoyaltiesResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function setPlay(i: number, patch: Partial<Play>) {
    setPlays((prev) => prev.map((p, j) => (j === i ? { ...p, ...patch } : p)));
  }

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const body = {
        budget,
        plays: plays.map((p) => ({ wallet: p.wallet, count: Number(p.count) })),
      };
      setRes(await postJson<RoyaltiesResponse>("/api/royalties", body));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="User-centric royalties" subtitle="Your budget pays only who you played (PA 05)">
      <Field label="Budget (USDC)">
        <input
          value={budget}
          onChange={(e) => setBudget(e.target.value)}
          className="w-32 rounded border border-outline-variant/40 bg-surface-container-lowest text-on-surface placeholder:text-outline px-2 py-1 font-mono"
        />
      </Field>

      <div className="mt-3 space-y-2">
        {plays.map((p, i) => (
          <div key={i} className="flex gap-2">
            <input
              value={p.wallet}
              onChange={(e) => setPlay(i, { wallet: e.target.value })}
              className="flex-1 rounded border border-outline-variant/40 bg-surface-container-lowest text-on-surface placeholder:text-outline px-2 py-1 font-mono text-xs"
              placeholder="0x creator"
            />
            <input
              value={p.count}
              onChange={(e) => setPlay(i, { count: e.target.value })}
              className="w-20 rounded border border-outline-variant/40 bg-surface-container-lowest text-on-surface placeholder:text-outline px-2 py-1 font-mono"
              placeholder="plays"
            />
          </div>
        ))}
        <button
          type="button"
          onClick={() => setPlays((prev) => [...prev, { wallet: "", count: "1" }])}
          className="text-sm text-primary-fixed-dim"
        >
          + creator
        </button>
      </div>

      <button
        type="button"
        onClick={submit}
        disabled={busy}
        className="mt-4 rounded bg-primary-fixed-dim px-4 py-2 text-on-primary-fixed font-bold disabled:opacity-50"
      >
        {busy ? "Settling…" : "Distribute by plays"}
      </button>

      <ErrorNote message={error} />

      {res && (
        <ul className="mt-4 space-y-1 text-sm">
          {res.recipients.map((r) => (
            <li key={r.wallet} className="flex items-center justify-between font-mono">
              <span className="truncate">{r.wallet.slice(0, 12)}… · {r.plays} plays</span>
              <span className="text-secondary-fixed-dim">{r.amount}</span>
            </li>
          ))}
          <li className="mt-1 border-t pt-1 text-xs text-on-surface-variant">
            gated out (sub-threshold): {res.gated_out} · total {res.total_settled} USDC
          </li>
        </ul>
      )}
    </Card>
  );
}
