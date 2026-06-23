"use client";

import { useCallback, useEffect, useState } from "react";
import { errorMessage, getJson, postJson } from "@/lib/api";
import type { BalanceResponse, TractionResponse } from "@/lib/capabilities";
import { Card, ErrorNote } from "./Card";

const KIND_LABEL: Record<string, string> = {
  payout: "Royalty splits",
  bond: "Reputation bonds",
  stream: "Streaming",
  royalty: "User royalties",
  qf: "Quadratic funding",
  retro: "Retroactive funding",
  send: "Memo'd sends",
  swap: "Stablecoin swaps",
  refund: "Refunds",
  request: "Split-bill requests",
  topup: "Prepaid credit top-ups",
  workflow: "Approved workflows",
  sweep: "Treasury sweeps",
  deposit: "Gateway deposits",
  gateway_spend: "Gateway spends",
  escrow: "Milestone escrow",
  order: "Order checkouts",
  schedule: "Recurring schedules",
};

// Relative share of total volume for one kind — a horizontal bar (no time series exists,
// so this shows the mix, not a trend).
function ShareBar({ value, total }: { value: number; total: number }) {
  const pct = total > 0 ? Math.min(100, (value / total) * 100) : 0;
  return (
    <div className="mt-0.5 h-1 w-full overflow-hidden rounded bg-white/5">
      <div className="h-full rounded bg-secondary-fixed-dim" style={{ width: `${pct}%` }} />
    </div>
  );
}

export function TractionPanel() {
  const [data, setData] = useState<TractionResponse | null>(null);
  const [bal, setBal] = useState<BalanceResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      setData(await getJson<TractionResponse>("/api/traction"));
      setBal(await getJson<BalanceResponse>("/api/balance"));
    } catch (err) {
      setError(errorMessage(err));
    }
  }, []);

  const generate = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const r = await postJson<{ traction: TractionResponse }>("/api/demo/run", { rounds: 3 });
      setData(r.traction);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }, []);

  const reset = useCallback(async () => {
    setError(null);
    try {
      const r = await postJson<{ traction: TractionResponse }>("/api/demo/reset", {});
      setData(r.traction);
    } catch (err) {
      setError(errorMessage(err));
    }
  }, []);

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
          className="rounded bg-primary-fixed-dim px-3 py-1.5 text-sm text-on-primary-fixed font-bold disabled:opacity-50"
        >
          {busy ? "Settling…" : "Generate sample volume"}
        </button>
        <button type="button" onClick={() => void reset()} className="rounded border px-3 py-1.5 text-sm">
          Reset
        </button>
      </div>

      <ErrorNote message={error} />

      {data && (
        <>
          <div className="mt-4 flex items-baseline gap-6">
            <div>
              <div className="text-2xl font-semibold text-secondary-fixed-dim">
                {data.total_volume_usdc} <span className="text-sm font-normal text-on-surface-variant">USDC</span>
              </div>
              <div className="text-xs text-on-surface-variant">total settled</div>
            </div>
            <div>
              <div className="text-2xl font-semibold">{data.total_payments}</div>
              <div className="text-xs text-on-surface-variant">payments</div>
            </div>
          </div>

          {bal && (
            <div className="mt-3 flex gap-6 border-t pt-3 text-sm">
              <div>
                <span className="font-semibold text-on-surface">{bal.credits.outstanding_usdc}</span>{" "}
                <span className="text-xs text-on-surface-variant">credits outstanding</span>
              </div>
              <div>
                <span className="font-semibold text-on-surface">{bal.requests.open}</span>{" "}
                <span className="text-xs text-on-surface-variant">
                  open requests ({bal.requests.outstanding_usdc} due)
                </span>
              </div>
              {bal.treasury && (
                <div>
                  <span className="font-semibold text-on-surface">{bal.treasury.balance}</span>{" "}
                  <span className="text-xs text-on-surface-variant">
                    treasury{bal.treasury.sweepable ? " (sweepable)" : ""}
                  </span>
                </div>
              )}
              {bal.gateway && (
                <div>
                  <span className="font-semibold text-on-surface">{bal.gateway.unified_usdc}</span>{" "}
                  <span className="text-xs text-on-surface-variant">gateway unified</span>
                </div>
              )}
              {bal.escrow && (
                <div>
                  <span className="font-semibold text-on-surface">{bal.escrow.locked_usdc}</span>{" "}
                  <span className="text-xs text-on-surface-variant">escrow locked ({bal.escrow.open} open)</span>
                </div>
              )}
              {bal.orders && bal.orders.total > 0 && (
                <div>
                  <span className="font-semibold text-on-surface">{bal.orders.total}</span>{" "}
                  <span className="text-xs text-on-surface-variant">orders ({bal.orders.pending} pending)</span>
                </div>
              )}
              {bal.schedules && bal.schedules.total > 0 && (
                <div>
                  <span className="font-semibold text-on-surface">{bal.schedules.committed_usdc}</span>{" "}
                  <span className="text-xs text-on-surface-variant">
                    scheduled ({bal.schedules.active} active)
                  </span>
                </div>
              )}
            </div>
          )}

          <ul className="mt-4 space-y-2 text-sm">
            {Object.entries(data.by_kind).map(([kind, s]) => (
              <li key={kind} className="font-mono">
                <div className="flex items-center justify-between">
                  <span className="text-on-surface-variant">{KIND_LABEL[kind] ?? kind}</span>
                  <span>
                    {s.count}× · <span className="text-secondary-fixed-dim">{s.volume_usdc}</span>
                  </span>
                </div>
                <ShareBar value={Number(s.volume_usdc)} total={Number(data.total_volume_usdc)} />
              </li>
            ))}
            {Object.keys(data.by_kind).length === 0 && (
              <li className="text-outline">No volume yet — use a panel to settle a payment.</li>
            )}
          </ul>
        </>
      )}
    </Card>
  );
}
