"use client";

import { useCallback, useEffect, useState } from "react";
import { errorMessage, getJson } from "@/lib/api";
import type { CitationMetrics } from "@/lib/capabilities";
import { Card, ErrorNote } from "./Card";

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <div className="text-xl font-semibold">{value}</div>
      <div className="text-xs text-gray-500">{label}</div>
    </div>
  );
}

export function MetricsPanel() {
  const [m, setM] = useState<CitationMetrics | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setM(await getJson<CitationMetrics>("/api/metrics"));
    } catch (err) {
      setError(errorMessage(err));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <Card title="Citation metrics" subtitle="The pay-on-citation ledger (prd.md §8 north-star)">
      <button type="button" onClick={() => void load()} className="rounded border px-3 py-1.5 text-sm">
        Refresh
      </button>
      <ErrorNote message={error} />
      {m && (
        <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-3">
          <Stat label="settled USDC" value={m.total_settled_usdc} />
          <Stat label="citations" value={m.citations_settled} />
          <Stat label="author wallets" value={m.distinct_author_wallets} />
          <Stat label="agent sessions" value={m.distinct_sessions} />
          <Stat label="external %" value={`${m.external_share_pct}%`} />
        </div>
      )}
    </Card>
  );
}
