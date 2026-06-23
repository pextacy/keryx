"use client";

import { useEffect, useMemo, useState } from "react";
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
  const [q, setQ] = useState("");
  const [limit, setLimit] = useState(50);
  const [error, setError] = useState<string | null>(null);

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

  const shown = useMemo(
    () =>
      rows
        .filter((r) => filter === "all" || (filter === "external" ? r.external : !r.external))
        .filter(
          (r) =>
            !q.trim() ||
            r.tx_hash.toLowerCase().includes(q.toLowerCase()) ||
            r.source_url.toLowerCase().includes(q.toLowerCase()),
        ),
    [rows, filter, q],
  );

  return (
    <main className="mx-auto mb-20 max-w-container-max px-gutter pt-24">
      <div className="mb-8">
        <h1 className="font-display-lg text-display-lg text-on-surface">Settlement Ledger</h1>
      </div>

      {error && (
        <div className="mb-6 flex items-center gap-3 rounded-lg border border-white/10 bg-surface-container-low p-4 text-sm text-on-surface-variant">
          <span className="material-symbols-outlined text-outline">cloud_off</span>
          <span>
            Agent offline — showing an empty ledger. Start it with{" "}
            <code className="text-primary-fixed-dim">make agent</code> to stream live settlements.
          </span>
        </div>
      )}

      {/* KPI header */}
      <div className="mb-12 grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
        <Kpi label="Total Settled" icon="account_balance_wallet" accent>
          <span className={metrics ? "" : "text-outline-variant"}>{metrics?.total_settled_usdc ?? "0.000000"}</span>
          <span className="ml-1 font-mono-data text-sm text-on-surface-variant">USDC</span>
        </Kpi>
        <Kpi label="Citations" icon="verified">
          <span className={metrics ? "" : "text-outline-variant"}>{metrics?.citations_settled ?? 0}</span>
        </Kpi>
        <Kpi label="Author Wallets" icon="groups">
          <span className={metrics ? "" : "text-outline-variant"}>{metrics?.distinct_author_wallets ?? 0}</span>
        </Kpi>
        <Kpi label="External Share" icon="share">
          <span className="flex items-baseline gap-3">
            <span className={metrics ? "" : "text-outline-variant"}>{metrics?.external_share_pct ?? 0}%</span>
            <span className="h-1 w-16 overflow-hidden rounded-full bg-surface-container-high">
              <span
                className="block h-full bg-secondary-fixed-dim shadow-[0_0_8px_#00e297]"
                style={{ width: `${Math.min(100, metrics?.external_share_pct ?? 0)}%` }}
              />
            </span>
          </span>
        </Kpi>
      </div>

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-12">
        {/* Settlement stream */}
        <div className="flex flex-col space-y-4 lg:col-span-8">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="flex items-center font-headline-md text-headline-md text-on-surface">
              <span className="material-symbols-outlined mr-2 text-primary-fixed-dim">view_list</span>
              Settlement Stream
            </h2>
            <div className="flex items-center gap-2">
              <div className="flex items-center space-x-2 rounded border border-white/5 bg-surface-container-low px-3 py-1">
                <span className="material-symbols-outlined text-body-md text-on-surface-variant">search</span>
                <input
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                  className="w-40 border-none bg-transparent py-1 font-mono-data text-mono-data text-on-surface placeholder:text-outline-variant focus:outline-none focus:ring-0"
                  placeholder="Filter by hash…"
                />
              </div>
              <select
                value={limit}
                onChange={(e) => setLimit(Number(e.target.value))}
                className="rounded border border-white/10 bg-surface-container-low px-2 py-1.5 font-label-caps text-[11px] text-on-surface"
              >
                {[25, 50, 100, 200].map((n) => (
                  <option key={n} value={n} className="bg-surface-container">
                    last {n}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {(["all", "team", "external"] as const).map((f) => (
              <button
                key={f}
                type="button"
                onClick={() => setFilter(f)}
                className={`rounded px-3 py-1.5 font-label-caps text-[11px] uppercase transition-all ${
                  filter === f
                    ? "bg-primary-fixed-dim text-on-primary-fixed"
                    : "border border-white/10 text-on-surface-variant hover:bg-white/5"
                }`}
              >
                {f}
              </button>
            ))}
            {shown.length > 0 && (
              <button
                type="button"
                onClick={() => downloadCsv(shown)}
                className="ml-auto flex items-center gap-1 rounded border border-white/10 px-3 py-1.5 font-label-caps text-[11px] text-on-surface-variant hover:bg-white/5"
              >
                <span className="material-symbols-outlined text-[16px]">download</span>
                CSV
              </button>
            )}
          </div>

          <div className="glass-card overflow-x-auto">
            <table className="w-full text-left">
              <thead className="border-b border-white/5 bg-surface-container-high/50">
                <tr>
                  <th className="px-6 py-4 font-label-caps text-label-caps text-on-surface-variant">Tx Hash</th>
                  <th className="px-6 py-4 font-label-caps text-label-caps text-on-surface-variant">Type</th>
                  <th className="px-6 py-4 text-right font-label-caps text-label-caps text-on-surface-variant">g</th>
                  <th className="px-6 py-4 text-right font-label-caps text-label-caps text-on-surface-variant">Value</th>
                  <th className="px-6 py-4 text-right font-label-caps text-label-caps text-on-surface-variant">Age</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {shown.map((r) => (
                  <tr
                    key={r.tx_hash + r.source_url}
                    className="group transition-colors hover:bg-primary-fixed-dim/5"
                  >
                    <td className="px-6 py-3">
                      <div className="flex items-center space-x-2">
                        <span className="material-symbols-outlined icon-fill text-body-md text-secondary-fixed-dim">
                          check_circle
                        </span>
                        <a
                          href={ARC_EXPLORER_TX + r.tx_hash}
                          target="_blank"
                          className="font-mono-data text-mono-data text-primary-fixed-dim group-hover:underline"
                        >
                          {r.tx_hash.slice(0, 10)}…
                        </a>
                        <Copy text={r.tx_hash} />
                      </div>
                      <div className="mt-0.5 max-w-[260px] truncate pl-7 text-[11px] text-outline" title={r.source_url}>
                        {r.source_url}
                      </div>
                    </td>
                    <td className="px-6 py-3">
                      <span
                        className={`border px-2 py-0.5 font-mono-data text-[10px] uppercase ${
                          r.external
                            ? "border-tertiary-fixed-dim/30 bg-on-tertiary-fixed-variant/20 text-tertiary-fixed-dim"
                            : "border-primary-fixed-dim/30 bg-on-primary-fixed-variant/20 text-primary-fixed-dim"
                        }`}
                      >
                        {r.external ? "External" : "Team"}
                      </span>
                    </td>
                    <td className="px-6 py-3 text-right font-mono-data text-mono-data text-on-surface-variant">
                      {r.g.toFixed(2)}
                    </td>
                    <td className="px-6 py-3 text-right font-mono-data text-mono-data text-secondary-fixed-dim">
                      {r.amount}
                    </td>
                    <td className="px-6 py-3 text-right font-mono-data text-mono-data text-on-surface-variant">
                      {ago(r.ts)}
                    </td>
                  </tr>
                ))}
                {shown.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-6 py-10 text-center font-label-caps text-label-caps text-outline">
                      {rows.length === 0
                        ? "No settlements yet — ask a question on the home page."
                        : `No ${filter} settlements match.`}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Side panel */}
        <aside className="flex flex-col space-y-8 lg:col-span-4">
          <div className="glass-card border-l-4 border-l-primary-fixed-dim p-6">
            <h3 className="mb-6 flex items-center font-headline-md text-[18px] text-on-surface">
              <span className="material-symbols-outlined mr-2 text-primary-fixed-dim">monitoring</span>
              Settlement Health
            </h3>

            <div className="mb-8">
              <div className="mb-2 flex items-end justify-between">
                <div>
                  <p className="font-label-caps text-[10px] uppercase text-on-surface-variant">Team vs External</p>
                  <p className="font-headline-md text-on-surface">
                    {metrics ? `${metrics.external_share_pct}%` : "—"}{" "}
                    <span className="text-sm font-normal text-on-surface-variant">external</span>
                  </p>
                </div>
                <span className="font-mono-data text-mono-data text-secondary-fixed-dim">
                  {metrics?.distinct_sessions ?? 0} sessions
                </span>
              </div>
              <div className="flex h-3 w-full overflow-hidden rounded-full bg-surface-container-high">
                <div
                  className="h-full bg-primary-fixed-dim"
                  style={{ width: `${100 - (metrics?.external_share_pct ?? 0)}%` }}
                  title="team"
                />
                <div
                  className="h-full bg-secondary-fixed-dim shadow-[0_0_8px_#00e297]"
                  style={{ width: `${metrics?.external_share_pct ?? 0}%` }}
                  title="external"
                />
              </div>
              <div className="mt-2 flex justify-between font-mono-data text-[11px]">
                <span className="text-primary-fixed-dim">team {metrics?.team.settled_usdc ?? "0"} USDC</span>
                <span className="text-secondary-fixed-dim">ext {metrics?.external.settled_usdc ?? "0"} USDC</span>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <MiniStat label="Citations" value={metrics?.citations_settled ?? 0} />
              <MiniStat label="Authors" value={metrics?.distinct_author_wallets ?? 0} />
            </div>
          </div>

          <div className="glass-card p-6">
            <h4 className="mb-2 font-headline-md text-[18px] text-primary-fixed-dim">Protocol Snapshot</h4>
            <p className="mb-4 text-body-md text-on-surface-variant">
              The ledger mirrors on-chain settlement — the chain is canonical. Every row links to its
              Arc explorer transaction so anyone can verify volume independently.
            </p>
            <div className="flex items-center space-x-2">
              <span className="material-symbols-outlined text-[16px] text-secondary-fixed-dim">verified_user</span>
              <span className="font-mono-data text-mono-data text-secondary-fixed-dim">
                {chainVerified ? "Chain-verified ledger" : "Mirror mode (verify off)"}
              </span>
            </div>
          </div>
        </aside>
      </div>
    </main>
  );
}

function Kpi({
  label,
  icon,
  accent,
  children,
}: {
  label: string;
  icon: string;
  accent?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="glass-card neon-border-bottom group p-6 transition-all duration-300 hover:bg-white/5">
      <div className="mb-4 flex items-center justify-between">
        <span className="font-label-caps text-label-caps uppercase text-on-surface-variant">{label}</span>
        <span className="material-symbols-outlined text-primary-fixed-dim opacity-50 transition-opacity group-hover:opacity-100">
          {icon}
        </span>
      </div>
      <div
        className={`flex items-baseline font-mono-data text-[30px] leading-none tracking-tight ${accent ? "text-primary-fixed-dim" : "text-on-surface"}`}
      >
        {children}
      </div>
    </div>
  );
}

function MiniStat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded border border-white/5 bg-surface-container-low p-3">
      <div className="font-label-caps text-[10px] uppercase text-on-surface-variant">{label}</div>
      <div className="mt-1 font-mono-data text-lg text-on-surface">{value}</div>
    </div>
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
