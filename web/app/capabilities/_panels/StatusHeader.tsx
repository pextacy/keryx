"use client";

import { useEffect, useState } from "react";
import { getJson } from "@/lib/api";
import type { StatusResponse } from "@/lib/capabilities";

function Badge({ label, on }: { label: string; on: boolean }) {
  return (
    <span
      className={`rounded-full border px-2 py-0.5 font-label-caps text-[10px] ${
        on
          ? "border-secondary-fixed-dim/30 bg-secondary-fixed-dim/10 text-secondary-fixed-dim"
          : "border-white/10 bg-white/5 text-on-surface-variant"
      }`}
    >
      {label}
    </span>
  );
}

type Metrics = { total_settled_usdc: string; citations_settled: number };

export function StatusHeader() {
  const [s, setS] = useState<StatusResponse | null>(null);
  const [m, setM] = useState<Metrics | null>(null);
  const [down, setDown] = useState(false);

  useEffect(() => {
    getJson<StatusResponse>("/api/status")
      .then(setS)
      .catch(() => setDown(true));
    // DB-backed citation totals persist across backend restarts, unlike the
    // in-memory traction book — so the headline isn't zero after a redeploy.
    getJson<Metrics>("/api/metrics")
      .then(setM)
      .catch(() => {});
  }, []);

  if (down) {
    return (
      <div className="mt-4 flex items-center gap-3 rounded-lg border border-white/10 bg-surface-container-low p-3 text-sm text-on-surface-variant">
        <span className="material-symbols-outlined text-outline">cloud_off</span>
        <span>
          Agent offline — start it with <code className="text-primary-fixed-dim">make agent</code> (or set{" "}
          <code className="text-primary-fixed-dim">AGENT_URL</code>) to drive these primitives live.
        </span>
      </div>
    );
  }
  if (!s) return null;

  // Persistent citation tolls (DB) + live primitive settlements (in-memory) so the
  // headline reflects everything that has cleared and survives a backend restart.
  const settledUsdc = (
    parseFloat(m?.total_settled_usdc ?? "0") + parseFloat(s.traction.total_volume_usdc ?? "0")
  ).toFixed(6);
  const settledCount = (m?.citations_settled ?? 0) + (s.traction.total_payments ?? 0);

  return (
    <div className="glass-card mt-4 flex flex-wrap items-center gap-2 p-3 text-sm">
      <span className="font-mono-data text-secondary-fixed-dim">{settledUsdc} USDC</span>
      <span className="text-on-surface-variant">settled · {settledCount} payments</span>
      <span className="mx-1 text-outline-variant">|</span>
      <Badge label={`rail: ${s.rail}`} on={s.rail !== "MockRail"} />
      <Badge label={s.embedder === "VoyageEmbedder" ? "dense embeddings" : "lexical"} on={s.embedder === "VoyageEmbedder"} />
      <Badge label="Gemini judge" on={s.llm_enabled} />
      <Badge label="ERC-8004" on={s.capabilities.erc8004} />
      <Badge label="ERC-8183" on={s.capabilities.erc8183} />
      <Badge label="Circle Wallets" on={s.capabilities.circle_wallets} />
      <Badge label="chain ledger" on={s.capabilities.chain_verified_ledger} />
      {s.books && (
        <>
          <span className="mx-1 text-outline-variant">|</span>
          <span className="font-mono-data text-xs text-on-surface-variant">
            {s.books.credits.outstanding_usdc} credits · {s.books.requests.open} open req ·{" "}
            {s.books.treasury.balance_usdc} treasury · {s.books.gateway.unified_usdc} gateway ·{" "}
            {s.books.escrow.locked_usdc} escrow · {s.books.orders.total} orders ·{" "}
            {s.books.schedules.active} schedules · {s.books.memos} memos
          </span>
        </>
      )}
    </div>
  );
}
