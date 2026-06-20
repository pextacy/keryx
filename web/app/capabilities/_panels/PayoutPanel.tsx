"use client";

import { useState } from "react";
import { errorMessage, postJson } from "@/lib/api";
import { ARC_EXPLORER_TX } from "@/lib/types";
import type { PayoutResponse } from "@/lib/capabilities";
import { Card, ErrorNote, Field } from "./Card";

interface Row {
  wallet: string;
  share: string;
}

const SEED: Row[] = [
  { wallet: "0x" + "a".repeat(40), share: "60" },
  { wallet: "0x" + "b".repeat(40), share: "30" },
  { wallet: "0x" + "c".repeat(40), share: "10" },
];

export function PayoutPanel() {
  const [amount, setAmount] = useState("0.01");
  const [rows, setRows] = useState<Row[]>(SEED);
  const [res, setRes] = useState<PayoutResponse | null>(null);
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
        amount,
        contributors: rows.map((r) => ({ wallet: r.wallet, share: r.share })),
      };
      setRes(await postJson<PayoutResponse>("/api/payout", body));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="Royalty split" subtitle="Pay every credited contributor in proportion (PA 04)">
      <Field label="Amount (USDC)">
        <input
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          className="w-32 rounded border border-gray-300 px-2 py-1 font-mono"
        />
      </Field>

      <div className="mt-3 space-y-2">
        {rows.map((r, i) => (
          <div key={i} className="flex gap-2">
            <input
              value={r.wallet}
              onChange={(e) => setRow(i, { wallet: e.target.value })}
              className="flex-1 rounded border border-gray-300 px-2 py-1 font-mono text-xs"
              placeholder="0x wallet"
            />
            <input
              value={r.share}
              onChange={(e) => setRow(i, { share: e.target.value })}
              className="w-20 rounded border border-gray-300 px-2 py-1 font-mono"
              placeholder="share"
            />
            <button
              type="button"
              onClick={() => setRows((prev) => prev.filter((_, j) => j !== i))}
              className="px-2 text-gray-400 hover:text-red-600"
            >
              ×
            </button>
          </div>
        ))}
        <button
          type="button"
          onClick={() => setRows((prev) => [...prev, { wallet: "", share: "1" }])}
          className="text-sm text-blue-600"
        >
          + contributor
        </button>
      </div>

      <button
        type="button"
        onClick={submit}
        disabled={busy}
        className="mt-4 rounded bg-black px-4 py-2 text-white disabled:opacity-50"
      >
        {busy ? "Settling…" : "Split & settle"}
      </button>

      <ErrorNote message={error} />

      {res && (
        <ul className="mt-4 space-y-1 text-sm">
          {res.recipients.map((r) => (
            <li key={r.wallet} className="flex items-center justify-between font-mono">
              <span className="truncate">{r.wallet.slice(0, 12)}… · share {r.share}</span>
              <span className="flex items-center gap-2">
                <span className="text-green-700">{r.amount}</span>
                {r.tx_hash && (
                  <a href={ARC_EXPLORER_TX + r.tx_hash} target="_blank" className="text-blue-600 underline">
                    tx
                  </a>
                )}
              </span>
            </li>
          ))}
          <li className="mt-1 flex justify-between border-t pt-1 font-mono text-green-700">
            <span>total settled</span>
            <span>{res.total_settled} USDC</span>
          </li>
        </ul>
      )}
    </Card>
  );
}
