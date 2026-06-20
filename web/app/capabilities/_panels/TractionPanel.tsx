"use client";

import { useCallback, useEffect, useState } from "react";
import { errorMessage, getJson, postJson } from "@/lib/api";
import type { TractionResponse } from "@/lib/capabilities";
import { Card, ErrorNote } from "./Card";

const KIND_LABEL: Record<string, string> = {
  payout: "Royalty splits",
  bond: "Reputation bonds",
  stream: "Streaming",
  royalty: "User royalties",
  qf: "Quadratic funding",
};

const w = (n: number) => "0x" + (0x1000 + n).toString(16).padStart(40, "0");

// One round of each primitive, fired from the browser so a reviewer can populate traction.
async function sampleRound(seed: number): Promise<void> {
  await postJson("/api/payout", {
    amount: "0.006",
    contributors: [
      { wallet: w(seed + 1), share: "3" },
      { wallet: w(seed + 2), share: "2" },
      { wallet: w(seed + 3), share: "1" },
    ],
  });
  await postJson("/api/royalties", {
    budget: "0.004",
    plays: [{ wallet: w(seed + 4), count: 8 }, { wallet: w(seed + 5), count: 2 }],
  });
  await postJson("/api/qf", {
    pool: "0.005",
    projects: [
      { wallet: w(seed + 6), contributions: ["1", "1", "1", "1"] },
      { wallet: w(seed + 7), contributions: ["4"] },
    ],
  });
  const bond = await postJson<{ bond_id: string }>("/api/bond", {
    provider: w(seed + 8),
    claimant: w(seed + 9),
    amount: "0.003",
  });
  await postJson(`/api/bond/${bond.bond_id}/resolve`, { passed: false });
  const s = await postJson<{ stream_id: string }>("/api/stream", {
    payer: w(seed),
    payee: w(seed + 1),
    rate: "0.001",
  });
  await postJson(`/api/stream/${s.stream_id}/tick`, { seconds: "3" });
  await postJson(`/api/stream/${s.stream_id}/close`, {});
}

export function TractionPanel() {
  const [data, setData] = useState<TractionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      setData(await getJson<TractionResponse>("/api/traction"));
    } catch (err) {
      setError(errorMessage(err));
    }
  }, []);

  const generate = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      for (let i = 0; i < 3; i++) await sampleRound(i * 10 + Math.floor(Math.random() * 900));
      await load();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }, [load]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <Card title="Traction" subtitle="Settled volume across every primitive (refreshes as you use them)">
      <div className="flex gap-2">
        <button type="button" onClick={() => void load()} className="rounded border px-3 py-1.5 text-sm">
          Refresh
        </button>
        <button
          type="button"
          onClick={() => void generate()}
          disabled={busy}
          className="rounded bg-black px-3 py-1.5 text-sm text-white disabled:opacity-50"
        >
          {busy ? "Settling…" : "Generate sample volume"}
        </button>
      </div>

      <ErrorNote message={error} />

      {data && (
        <>
          <div className="mt-4 flex items-baseline gap-6">
            <div>
              <div className="text-2xl font-semibold text-green-700">
                {data.total_volume_usdc} <span className="text-sm font-normal text-gray-500">USDC</span>
              </div>
              <div className="text-xs text-gray-500">total settled</div>
            </div>
            <div>
              <div className="text-2xl font-semibold">{data.total_payments}</div>
              <div className="text-xs text-gray-500">payments</div>
            </div>
          </div>

          <ul className="mt-4 space-y-1 text-sm">
            {Object.entries(data.by_kind).map(([kind, s]) => (
              <li key={kind} className="flex items-center justify-between font-mono">
                <span className="text-gray-600">{KIND_LABEL[kind] ?? kind}</span>
                <span>
                  {s.count}× · <span className="text-green-700">{s.volume_usdc}</span>
                </span>
              </li>
            ))}
            {Object.keys(data.by_kind).length === 0 && (
              <li className="text-gray-400">No volume yet — use a panel to settle a payment.</li>
            )}
          </ul>
        </>
      )}
    </Card>
  );
}
