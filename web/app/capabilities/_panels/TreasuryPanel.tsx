"use client";

import { useCallback, useEffect, useState } from "react";
import { errorMessage, getJson, postJson } from "@/lib/api";
import type { TreasuryResponse } from "@/lib/capabilities";
import { useToast } from "@/app/Toast";
import { Card, ErrorNote, Field } from "./Card";
import { TxLink } from "./TxLink";

// Treasury management (ported from arc-fintech): the treasury accumulates prepaid-credit
// top-ups; once the balance crosses the threshold it's "sweepable" and can be swept to a
// destination wallet (the offline analogue of a multi-chain rebalance).
export function TreasuryPanel() {
  const { toast, notify } = useToast();
  const [data, setData] = useState<TreasuryResponse | null>(null);
  const [dest, setDest] = useState("0x" + "f".repeat(40));
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      setData(await getJson<TreasuryResponse>("/api/treasury"));
    } catch (err) {
      setError(errorMessage(err));
    }
  }, []);

  async function sweep() {
    setBusy(true);
    setError(null);
    try {
      const r = await postJson<TreasuryResponse>("/api/treasury/sweep", { to: dest });
      if (r.error) setError(r.error);
      else {
        setData(r);
        if (r.swept) notify(`Swept ${r.amount} USDC`, r.tx_hash);
      }
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <Card
      title="Treasury (fintech)"
      subtitle="Prepaid top-ups accumulate here; sweep to a destination once over threshold"
    >
      <div className="flex gap-2">
        <button type="button" onClick={() => void load()} className="rounded border px-3 py-1.5 text-sm">
          Refresh
        </button>
      </div>

      {data && (
        <>
          <div className="mt-4 flex items-baseline gap-2">
            <span className="text-2xl font-semibold text-secondary-fixed-dim">{data.balance}</span>
            <span className="text-sm text-on-surface-variant">USDC in treasury</span>
            {data.sweepable && (
              <span className="rounded bg-error-container/20 px-2 py-0.5 text-xs font-medium text-error">
                sweepable
              </span>
            )}
          </div>
          <div className="mt-1 text-xs text-on-surface-variant">sweep threshold {data.threshold} USDC</div>

          <div className="mt-3 flex items-end gap-2">
            <Field label="Sweep to">
              <input
                value={dest}
                onChange={(e) => setDest(e.target.value)}
                className="w-full rounded border border-outline-variant/40 bg-surface-container-lowest text-on-surface placeholder:text-outline px-2 py-1 font-mono text-xs"
              />
            </Field>
            <button
              type="button"
              onClick={() => void sweep()}
              disabled={busy || Number(data.balance) <= 0}
              className="mb-1 rounded bg-primary-fixed-dim px-3 py-1.5 text-sm text-on-primary-fixed font-bold disabled:opacity-50"
            >
              {busy ? "…" : "Sweep"}
            </button>
          </div>

          {data.flows.length > 0 ? (
            <ul className="mt-4 space-y-1 text-xs">
              {data.flows
                .slice()
                .reverse()
                .map((f, i) => (
                  <li key={i} className="flex items-center justify-between gap-2 font-mono">
                    <span className={f.kind === "deposit" ? "text-secondary-fixed-dim" : "text-primary-fixed-dim"}>
                      {f.kind === "deposit" ? "+" : "→"}
                      {f.amount} · {f.kind}
                    </span>
                    {f.tx_hash && <TxLink hash={f.tx_hash} prefix="tx" />}
                  </li>
                ))}
            </ul>
          ) : (
            <p className="mt-4 text-xs text-outline">
              no flows yet — top up prepaid credits to fund the treasury
            </p>
          )}
        </>
      )}

      <ErrorNote message={error} />
      {toast}
    </Card>
  );
}
