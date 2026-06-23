"use client";

import { useEffect, useState } from "react";
import { ARC_EXPLORER_TX, ARC_NETWORK, safeHref, type AskResponse } from "@/lib/types";
import { Copy } from "./Copy";

type Activity = { settlements: number; volume_usdc: string };
type Settlement = { seq: number; kind: string; amount: string };

export default function Home() {
  const [activity, setActivity] = useState<Activity | null>(null);
  const [recent, setRecent] = useState<Settlement[]>([]);

  useEffect(() => {
    fetch("/api/healthz", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((b) => b?.activity && setActivity(b.activity))
      .catch(() => {});
    fetch("/api/history?limit=3", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((b) => b?.settlements && setRecent(b.settlements))
      .catch(() => {});
  }, []);

  const [query, setQuery] = useState(
    "How do Gateway nanopayments settle sub-cent USDC on Arc?",
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [res, setRes] = useState<AskResponse | null>(null);
  const [tipped, setTipped] = useState<Record<string, string>>({});

  async function tip(sourceUrl: string, wallet: string) {
    try {
      const r = await fetch("/api/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ to: wallet, amount: "0.001", memo: `tip: ${sourceUrl}` }),
      });
      const data = await r.json();
      if (data.tx_hash) setTipped((p) => ({ ...p, [sourceUrl]: data.tx_hash }));
    } catch {
      // best-effort tip; ignore
    }
  }

  async function ask(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setRes(null);
    try {
      const r = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.message ?? data.error ?? "request failed");
      setRes(data as AskResponse);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  const cited = res?.citations.filter((c) => c.cited) ?? [];
  const skipped = res?.citations.filter((c) => !c.cited) ?? [];

  return (
    <main className="relative mx-auto max-w-container-max px-gutter pb-24 pt-28">
      {/* Hero */}
      <section className="relative mb-14 text-center">
        <div className="mb-6 inline-block animate-pulse rounded-full border border-primary-fixed-dim/20 bg-primary-fixed-dim/5 px-4 py-1 font-label-caps text-label-caps text-primary-fixed-dim">
          {ARC_NETWORK === "mainnet" ? "Arc Mainnet" : "Arc Testnet"} · Pay-on-citation
        </div>
        <h1 className="mb-6 font-display-lg text-display-lg tracking-tight text-white md:text-[64px] md:leading-[72px]">
          The{" "}
          <span className="bg-gradient-to-r from-primary-fixed-dim to-secondary-fixed-dim bg-clip-text text-transparent">
            Citation-Toll Payment Layer
          </span>
          <br className="hidden md:block" /> for the Agent Web
        </h1>
        <p className="mx-auto mb-8 max-w-2xl text-body-md text-on-surface-variant">
          Your work earns every time an agent cites it. Ask a question; the agent pays every
          source it genuinely cites — sub-cent USDC, live on Arc.
        </p>

        {/* Query input */}
        <form onSubmit={ask} className="group relative mx-auto max-w-3xl">
          <div className="absolute inset-0 bg-primary-fixed-dim/10 opacity-0 blur-xl transition-opacity group-focus-within:opacity-100" />
          <div className="neon-glow-primary relative flex items-center overflow-hidden rounded-xl border border-white/10 bg-surface-container-lowest p-1 transition-all duration-300 focus-within:ring-1 focus-within:ring-primary-fixed-dim">
            <span className="material-symbols-outlined ml-4 text-on-surface-variant">search</span>
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="w-full border-none bg-transparent px-4 py-4 text-body-md text-white placeholder-on-surface-variant/50 focus:outline-none focus:ring-0"
              placeholder="Query the agent web via paid inference…"
            />
            <button
              type="submit"
              disabled={loading}
              className="mr-1 shrink-0 rounded-lg bg-primary-fixed-dim px-8 py-3 font-label-caps text-label-caps font-bold text-on-primary-fixed transition-transform hover:brightness-110 active:scale-95 disabled:opacity-50"
            >
              {loading ? "RESEARCHING…" : "EXECUTE"}
            </button>
          </div>
          <div className="mt-5 flex flex-wrap justify-center gap-2 font-label-caps text-[10px] text-on-surface-variant">
            {[
              ["bolt", "Pay-on-citation, not pay-on-fetch"],
              ["verified", "Signed attestation per answer"],
              ["payments", "Sub-cent USDC on Arc"],
            ].map(([icon, label]) => (
              <span
                key={label}
                className="flex items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.03] px-3 py-1.5"
              >
                <span className="material-symbols-outlined text-[14px] text-primary-fixed-dim">{icon}</span>
                {label}
              </span>
            ))}
          </div>
        </form>
      </section>

      {/* Traction strip */}
      <section className="mb-14 grid grid-cols-1 gap-6 md:grid-cols-3">
        <div className="glass-card flex flex-col space-y-2 border-l-2 border-l-primary-fixed-dim p-6">
          <span className="font-label-caps text-label-caps text-on-surface-variant">Total Settled USDC</span>
          <div className="flex items-baseline space-x-2">
            <span className={`font-mono-data text-2xl ${activity ? "text-white" : "text-outline-variant"}`}>
              {activity?.volume_usdc ?? "0.000000"}
            </span>
            <span className="font-mono-data text-xs text-secondary-fixed-dim">
              {activity ? "across every primitive" : "awaiting agent"}
            </span>
          </div>
        </div>
        <div className="glass-card flex flex-col space-y-2 border-l-2 border-l-secondary-fixed-dim p-6">
          <span className="font-label-caps text-label-caps text-on-surface-variant">Payments Settled</span>
          <div className="flex items-baseline space-x-2">
            <span className={`font-mono-data text-2xl ${activity ? "text-white" : "text-outline-variant"}`}>
              {activity?.settlements ?? "0"}
            </span>
            <span className="font-mono-data text-xs text-secondary-fixed-dim">citation tolls</span>
          </div>
        </div>
        <div className="glass-card flex flex-col space-y-2 border-l-2 border-l-on-surface-variant p-6">
          <span className="font-label-caps text-label-caps text-on-surface-variant">Last Movements</span>
          <div className="flex flex-col space-y-1">
            {recent.length === 0 && (
              <span className="font-mono-data text-[11px] text-outline">no settlements yet</span>
            )}
            {recent.map((s) => (
              <div key={s.seq} className="flex justify-between font-mono-data text-[11px]">
                <span className="text-on-surface-variant">{s.kind}</span>
                <span className="text-secondary-fixed-dim">{s.amount} USDC</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {error && (
        <p className="mb-8 rounded-lg border border-error/30 bg-error-container/20 p-4 text-error">
          {error}
        </p>
      )}

      {/* Post-response state */}
      {res && (
        <section className="grid grid-cols-1 items-start gap-8 lg:grid-cols-12">
          {/* Answer + citations */}
          <div className="space-y-6 lg:col-span-8">
            <div className="glass-card relative overflow-hidden p-8">
              <div className="absolute left-0 top-0 h-full w-1 bg-primary-fixed-dim" />
              <div className="mb-6 flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary-fixed-dim/20">
                    <span className="material-symbols-outlined text-primary-fixed-dim">smart_toy</span>
                  </div>
                  <div className="text-left">
                    <h3 className="font-headline-md text-[18px] text-white">Keryx Research Agent</h3>
                    <p className="text-xs text-on-surface-variant">
                      {cited.length} cited · {skipped.length} evaluated, not cited
                    </p>
                  </div>
                </div>
                <span className="rounded border border-secondary-fixed-dim/20 bg-secondary-fixed-dim/10 px-2 py-1 font-label-caps text-[10px] text-secondary-fixed-dim">
                  SETTLED {res.total_settled} USDC
                </span>
              </div>
              <p className="whitespace-pre-wrap text-body-md leading-relaxed text-on-surface">
                {res.answer}
              </p>
            </div>

            {/* Cited & paid */}
            <div className="space-y-4">
              <h4 className="font-label-caps text-label-caps text-primary-fixed-dim">
                Cited &amp; Paid Grounding Sources
              </h4>
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                {cited.map((c, i) => (
                  <div
                    key={c.source_url}
                    className="glass-card flex flex-col gap-3 p-4 transition-colors hover:border-secondary-fixed-dim/40"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex min-w-0 items-center gap-3">
                        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded bg-surface-container-highest font-mono-data text-xs">
                          {String(i + 1).padStart(2, "0")}
                        </div>
                        <a
                          href={safeHref(c.source_url)}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="min-w-0 truncate text-sm font-semibold text-white hover:text-primary-fixed-dim"
                          title={c.source_url}
                        >
                          {c.source_url}
                        </a>
                      </div>
                      <div className="shrink-0 text-right">
                        <div className="font-mono-data text-sm text-secondary-fixed-dim">
                          {c.g.toFixed(2)}
                        </div>
                        <div className="font-label-caps text-[9px] text-on-surface-variant">GROUNDING</div>
                      </div>
                    </div>
                    <div className="flex items-center justify-between border-t border-white/5 pt-2 font-mono-data text-xs">
                      <span className="text-secondary-fixed-dim">{c.amount} USDC</span>
                      <span className="flex items-center gap-3">
                        {c.tx_hash && (
                          <a
                            href={ARC_EXPLORER_TX + c.tx_hash}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-primary-fixed-dim underline"
                          >
                            tx
                          </a>
                        )}
                        {c.author_wallet &&
                          (tipped[c.source_url] ? (
                            <a
                              href={ARC_EXPLORER_TX + tipped[c.source_url]}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-tertiary-fixed-dim underline"
                            >
                              tipped ✓
                            </a>
                          ) : (
                            <button
                              type="button"
                              onClick={() => tip(c.source_url, c.author_wallet as string)}
                              className="rounded border border-tertiary-fixed-dim/40 px-1.5 text-[11px] text-tertiary-fixed-dim hover:bg-tertiary-fixed-dim/10"
                            >
                              tip $0.001
                            </button>
                          ))}
                      </span>
                    </div>
                  </div>
                ))}
              </div>

              {skipped.length > 0 && (
                <>
                  <h4 className="pt-2 font-label-caps text-label-caps text-on-surface-variant">
                    Evaluated, not cited ({skipped.length}) — proof we pay on citation, not fetch
                  </h4>
                  <div className="glass-card divide-y divide-white/5">
                    {skipped.map((c) => (
                      <div
                        key={c.source_url}
                        className="flex items-center justify-between px-4 py-2 text-sm text-outline"
                      >
                        <span className="min-w-0 truncate" title={c.source_url}>
                          {c.source_url}
                        </span>
                        <span className="shrink-0 font-mono-data text-xs">
                          g={c.g.toFixed(2)} · $0
                        </span>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>
          </div>

          {/* Attestation sidebar */}
          <div className="space-y-6 lg:col-span-4">
            <div
              className={`glass-card relative overflow-hidden ${res.attestation.verified ? "neon-glow-success" : ""}`}
            >
              {res.attestation.verified && <div className="scanning-line" />}
              <div className="p-6">
                <div className="mb-4 flex items-center space-x-2">
                  <span
                    className={`material-symbols-outlined icon-fill ${res.attestation.verified ? "text-secondary-fixed-dim" : "text-error"}`}
                  >
                    {res.attestation.verified ? "verified_user" : "gpp_bad"}
                  </span>
                  <h4 className="font-label-caps text-label-caps text-white">Attestation Verdict</h4>
                </div>
                <div className="mb-6 flex aspect-square flex-col items-center justify-center space-y-4 rounded border border-secondary-fixed-dim/10 bg-black/40 p-4 text-center">
                  <div className="relative">
                    <span
                      className={`material-symbols-outlined text-6xl ${res.attestation.verified ? "text-secondary-fixed-dim" : "text-error"}`}
                    >
                      {res.attestation.verified ? "verified" : "report"}
                    </span>
                    {res.attestation.verified && (
                      <div className="absolute -right-1 -top-1 h-3 w-3 animate-ping rounded-full bg-secondary-fixed-dim" />
                    )}
                  </div>
                  <div className="space-y-1">
                    <p
                      className={`font-mono-data text-lg ${res.attestation.verified ? "text-secondary-fixed-dim" : "text-error"}`}
                    >
                      {res.attestation.verified ? "PROVEN_TRUST" : "INVALID_SIG"}
                    </p>
                    <p className="text-[10px] uppercase tracking-widest text-on-surface-variant">
                      sig {(res.attestation.signature ?? "—").slice(0, 10)}…
                    </p>
                  </div>
                </div>
                <ul className="space-y-3 text-xs">
                  <li className="flex items-center justify-between gap-2">
                    <span className="shrink-0 text-on-surface-variant">Agent</span>
                    <span className="flex min-w-0 items-center gap-1 font-mono-data text-white">
                      <span className="truncate" title={res.attestation.agent_pubkey}>
                        {res.attestation.agent_pubkey.slice(0, 14)}…
                      </span>
                      <Copy text={res.attestation.agent_pubkey} />
                    </span>
                  </li>
                  <li className="flex items-center justify-between gap-2">
                    <span className="shrink-0 text-on-surface-variant">Query hash</span>
                    <span className="flex min-w-0 items-center gap-1 font-mono-data text-white">
                      <span className="truncate" title={res.attestation.query_hash}>
                        {res.attestation.query_hash.slice(0, 14)}…
                      </span>
                      <Copy text={res.attestation.query_hash} />
                    </span>
                  </li>
                  <li className="flex items-center justify-between gap-2">
                    <span className="shrink-0 text-on-surface-variant">Answer hash</span>
                    <span className="flex min-w-0 items-center gap-1 font-mono-data text-white">
                      <span className="truncate" title={res.attestation.answer_hash}>
                        {res.attestation.answer_hash.slice(0, 14)}…
                      </span>
                      <Copy text={res.attestation.answer_hash} />
                    </span>
                  </li>
                  <li className="flex items-center justify-between">
                    <span className="text-on-surface-variant">Citation tolls</span>
                    <span className="font-mono-data text-white">{res.total_settled} USDC</span>
                  </li>
                </ul>
                <a
                  href="/audit"
                  className="mt-6 block w-full border border-secondary-fixed-dim/40 bg-secondary-fixed-dim/10 py-3 text-center font-label-caps text-xs text-secondary-fixed-dim transition-all hover:bg-secondary-fixed-dim/20"
                >
                  VERIFY THIS ATTESTATION →
                </a>
              </div>
            </div>
          </div>
        </section>
      )}

      {/* How it works — a real sequence, so the numbering carries meaning */}
      {!res && (
        <section className="mt-4">
          <div className="mb-6 flex items-center gap-3">
            <span className="font-label-caps text-label-caps text-on-surface-variant">How a toll clears</span>
            <span className="h-px flex-1 bg-white/10" />
          </div>
          <div className="grid grid-cols-1 gap-px overflow-hidden rounded-xl border border-white/10 bg-white/10 md:grid-cols-3">
            {[
              {
                n: "01",
                icon: "search",
                title: "Ask",
                body: "Pose a question. The agent retrieves candidate sources and scores how much each one grounds the answer.",
              },
              {
                n: "02",
                icon: "fact_check",
                title: "Cite",
                body: "Only sources the answer genuinely relies on are cited. The rest are evaluated and skipped — visibly, at zero cost.",
              },
              {
                n: "03",
                icon: "bolt",
                title: "Settle",
                body: "Each cited author is paid a sub-cent USDC toll on Arc, bound to a signed attestation and an on-chain receipt.",
              },
            ].map((step) => (
              <div key={step.n} className="group bg-surface-container-lowest/80 p-6 transition-colors hover:bg-white/[0.03]">
                <div className="mb-4 flex items-center justify-between">
                  <span className="font-mono-data text-2xl text-outline-variant transition-colors group-hover:text-primary-fixed-dim">
                    {step.n}
                  </span>
                  <span className="material-symbols-outlined text-primary-fixed-dim">{step.icon}</span>
                </div>
                <h3 className="font-headline-md text-[18px] text-on-surface">{step.title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-on-surface-variant">{step.body}</p>
              </div>
            ))}
          </div>
        </section>
      )}
    </main>
  );
}
