"use client";

import { useState } from "react";
import { errorMessage, postJson } from "@/lib/api";
import { ARC_EXPLORER_TX } from "@/lib/types";
import type { BondResponse } from "@/lib/capabilities";
import { Card, ErrorNote, Field } from "./Card";

export function BondPanel() {
  const [provider, setProvider] = useState("0x" + "1".repeat(40));
  const [claimant, setClaimant] = useState("0x" + "2".repeat(40));
  const [amount, setAmount] = useState("0.01");
  const [bond, setBond] = useState<BondResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function run(fn: () => Promise<BondResponse>) {
    setBusy(true);
    setError(null);
    try {
      setBond(await fn());
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  const post = () =>
    run(() => postJson<BondResponse>("/api/bond", { provider, claimant, amount }));

  const resolve = (passed: boolean) => {
    if (!bond) return;
    void run(() =>
      postJson<BondResponse>(`/api/bond/${encodeURIComponent(bond.bond_id)}/resolve`, { passed }),
    );
  };

  return (
    <Card title="Reputation bond" subtitle="Collateral that slashes to the claimant on default (PA 08)">
      <Field label="Provider (posts the bond)">
        <input
          value={provider}
          onChange={(e) => setProvider(e.target.value)}
          className="w-full rounded border border-gray-300 px-2 py-1 font-mono text-xs"
        />
      </Field>
      <div className="mt-2">
        <Field label="Claimant (paid if slashed)">
          <input
            value={claimant}
            onChange={(e) => setClaimant(e.target.value)}
            className="w-full rounded border border-gray-300 px-2 py-1 font-mono text-xs"
          />
        </Field>
      </div>
      <div className="mt-2">
        <Field label="Bond (USDC)">
          <input
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            className="w-32 rounded border border-gray-300 px-2 py-1 font-mono"
          />
        </Field>
      </div>

      <div className="mt-4 flex gap-2">
        <button
          type="button"
          onClick={post}
          disabled={busy}
          className="rounded bg-black px-3 py-1.5 text-sm text-white disabled:opacity-50"
        >
          Post bond
        </button>
        <button
          type="button"
          onClick={() => resolve(true)}
          disabled={busy || !bond}
          className="rounded border border-green-600 px-3 py-1.5 text-sm text-green-700 disabled:opacity-40"
        >
          Resolve: delivered
        </button>
        <button
          type="button"
          onClick={() => resolve(false)}
          disabled={busy || !bond}
          className="rounded border border-red-600 px-3 py-1.5 text-sm text-red-700 disabled:opacity-40"
        >
          Resolve: slash
        </button>
      </div>

      <ErrorNote message={error} />

      {bond && (
        <dl className="mt-4 space-y-1 font-mono text-sm">
          <div className="flex justify-between">
            <span className="text-gray-500">bond</span>
            <span>{bond.bond_id}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">status</span>
            <span className={bond.status === "slashed" ? "text-red-700" : "text-green-700"}>
              {bond.status}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">reputation Δ</span>
            <span>{bond.reputation_delta}</span>
          </div>
          {bond.tx_hash && (
            <div className="flex justify-between">
              <span className="text-gray-500">slash tx</span>
              <a href={ARC_EXPLORER_TX + bond.tx_hash} target="_blank" className="text-blue-600 underline">
                {bond.tx_hash.slice(0, 14)}…
              </a>
            </div>
          )}
        </dl>
      )}
    </Card>
  );
}
