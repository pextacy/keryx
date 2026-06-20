"use client";

import { useCallback, useEffect, useState } from "react";
import { errorMessage, getJson } from "@/lib/api";
import type { TractionResponse } from "@/lib/capabilities";
import { Card, ErrorNote } from "./Card";

const KIND_LABEL: Record<string, string> = {
  payout: "Royalty splits",
  bond: "Reputation bonds",
  stream: "Streaming",
  royalty: "User royalties",
  qf: "Quadratic funding",
};

export function TractionPanel() {
  const [data, setData] = useState<TractionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setData(await getJson<TractionResponse>("/api/traction"));
    } catch (err) {
      setError(errorMessage(err));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <Card title="Traction" subtitle="Settled volume across every primitive (refreshes as you use them)">
      <button type="button" onClick={() => void load()} className="rounded border px-3 py-1.5 text-sm">
        Refresh
      </button>

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
