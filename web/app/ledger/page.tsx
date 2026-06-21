"use client";

import { useEffect, useState } from "react";
import { ARC_EXPLORER_TX } from "@/lib/types";
import { Copy } from "../Copy";

interface Metrics {
  total_settled_usdc: string;
  citations_settled: number;
  distinct_author_wallets: number;
  distinct_sessions: number;
  team: { citations: number; settled_usdc: string };
  external: { citations: number; settled_usdc: string };
  external_share_pct: number;
}
interface Row {
  source_url: string;
  author_wallet: string | null;
  g: number;
  amount: string;
  tx_hash: string;
  external: boolean;
  ts: number;
}

export default function LedgerPage() {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [rows, setRows] = useState<Row[]>([]);
  const [chainVerified, setChainVerified] = useState(false);
  const [filter, setFilter] = useState<"all" | "team" | "external">("all");
  const [limit, setLimit] = useState(50);
  const [error, setError] = useState<string | null>(null);

  const shown = rows.filter(
    (r) => filter === "all" || (filter === "external" ? r.external : !r.external),
  );

  useEffect(() => {
    const load = async () => {
      try {
        const r = await fetch(`/api/ledger?limit=${limit}`, { cache: "no-store" });
        const data = await r.json();
        if (!r.ok) throw new Error(data.message ?? "failed");
        setMetrics(data.metrics);
        setRows(data.recent ?? []);
        setChainVerified(Boolean(data.chain_verified));
      } catch (err) {
        setError((err as Error).message);
      }
    };
    load();
    const id = setInterval(load, 4000); // live-ish refresh
    return () => clearInterval(id);
  }, [limit]);

  return (
    <main className="mx-auto max-w-4xl p-8">
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-semibold">Settlement ledger</h1>
        <span
          className={`rounded-full px-2 py-0.5 text-xs ${chainVerified ? "bg-green-100 text-green-800" : "bg-gray-100 text-gray-500"}`}
        >
          {chainVerified ? "chain-verified" : "mirror (chain verify off)"}
        </span>
      </div>
      <p className="mt-1 text-sm text-gray-500">
        Mirrors on-chain settlement — chain is canonical. Team vs external volume labeled.
      </p>
      <div className="mt-3 flex items-center gap-2">
        {(["all", "team", "external"] as const).map((f) => (
          <button
            key={f}
            type="button"
            onClick={() => setFilter(f)}
            className={`rounded px-3 py-1.5 text-sm ${filter === f ? "bg-black text-white" : "border"}`}
          >
            {f}
          </button>
        ))}
        <select
          value={limit}
          onChange={(e) => setLimit(Number(e.target.value))}
          className="ml-auto rounded border px-2 py-1.5 text-sm"
        >
          {[25, 50, 100, 200].map((n) => (
            <option key={n} value={n}>
              last {n}
            </option>
          ))}
        </select>
        {rows.length > 0 && (
          <button
            type="button"
            onClick={() => downloadCsv(shown)}
            className="rounded border px-3 py-1.5 text-sm"
          >
            Download CSV
          </button>
        )}
      </div>
      {error && <p className="mt-4 rounded bg-red-50 p-3 text-red-700">{error}</p>}

      {metrics && (
        <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat label="Total settled" value={`${metrics.total_settled_usdc} USDC`} />
          <Stat label="Citations" value={metrics.citations_settled} />
          <Stat label="Author wallets" value={metrics.distinct_author_wallets} />
          <Stat label="External share" value={`${metrics.external_share_pct}%`} />
        </div>
      )}

      <table className="mt-8 w-full text-left text-sm">
        <thead className="text-gray-500">
          <tr>
            <th className="py-2">Source</th>
            <th>g</th>
            <th>Amount</th>
            <th>Who</th>
            <th>When</th>
            <th>Tx</th>
          </tr>
        </thead>
        <tbody>
          {shown.map((r) => (
            <tr key={r.tx_hash + r.source_url} className="border-t border-gray-100">
              <td className="py-2">{r.source_url}</td>
              <td className="font-mono">{r.g.toFixed(2)}</td>
              <td className="font-mono text-green-700">{r.amount}</td>
              <td>
                <span className={r.external ? "text-purple-600" : "text-gray-400"}>
                  {r.external ? "external" : "team"}
                </span>
              </td>
              <td className="text-gray-400">{ago(r.ts)}</td>
              <td className="flex items-center gap-1 py-2">
                <a
                  href={ARC_EXPLORER_TX + r.tx_hash}
                  target="_blank"
                  className="text-blue-600 underline"
                >
                  {r.tx_hash.slice(0, 10)}…
                </a>
                <Copy text={r.tx_hash} />
              </td>
            </tr>
          ))}
          {shown.length === 0 && (
            <tr>
              <td colSpan={6} className="py-6 text-center text-gray-400">
                {rows.length === 0
                  ? "No settlements yet — ask a question on the home page."
                  : `No ${filter} settlements.`}
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </main>
  );
}

function downloadCsv(rows: Row[]): void {
  const header = "source_url,author_wallet,g,amount,tx_hash,external,ts";
  const body = rows
    .map((r) =>
      [r.source_url, r.author_wallet ?? "", r.g, r.amount, r.tx_hash, r.external, r.ts]
        .map((v) => `"${String(v).replace(/"/g, '""')}"`)
        .join(","),
    )
    .join("\n");
  const blob = new Blob([`${header}\n${body}`], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "keryx-ledger.csv";
  a.click();
  URL.revokeObjectURL(url);
}

function ago(ts: number): string {
  const s = Math.max(0, Math.floor(Date.now() / 1000 - ts));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  return `${Math.floor(s / 3600)}h ago`;
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded border border-gray-200 p-3">
      <div className="text-xs text-gray-500">{label}</div>
      <div className="mt-1 text-lg font-semibold">{value}</div>
    </div>
  );
}
