"use client";

import { useEffect, useMemo, useState } from "react";
import { errorMessage, getJson, postJson } from "@/lib/api";
import { ARC_EXPLORER_TX } from "@/lib/types";
import { Copy } from "../Copy";

interface VerifyResult {
  verified: boolean;
  agent_pubkey: string;
  query_hash: string;
  citations: number;
}

interface MemoResult {
  tx_hash: string;
  found: boolean;
  memo: string | null;
}

interface MemoItem {
  tx_hash: string;
  memo: string;
}

interface ThreadItem {
  tx_hash: string;
  memo: string | null;
  meta?: { kind?: string } | null;
}

interface ThreadResult {
  found: boolean;
  ancestors: ThreadItem[];
  replies: ThreadItem[];
}

interface CircleResult {
  enabled: boolean;
  tx_id?: string;
  transaction?: unknown;
  error?: string;
}

const PLACEHOLDER = `{
  "query_hash": "0x…",
  "answer_hash": "0x…",
  "citations": [],
  "agent_pubkey": "0x…",
  "ts": 0,
  "signature": "0x…"
}`;

export default function AuditPage() {
  const [text, setText] = useState("");
  const [res, setRes] = useState<VerifyResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [tx, setTx] = useState("");
  const [memo, setMemo] = useState<MemoResult | null>(null);
  const [thread, setThread] = useState<ThreadResult | null>(null);
  const [feed, setFeed] = useState<MemoItem[]>([]);
  const [circleId, setCircleId] = useState("");
  const [circle, setCircle] = useState<CircleResult | null>(null);
  const [circleBusy, setCircleBusy] = useState(false);

  useEffect(() => {
    getJson<{ memos: MemoItem[] }>("/api/memos")
      .then((d) => setFeed(d.memos))
      .catch(() => setFeed([]));
  }, [memo]);

  async function verify() {
    setBusy(true);
    setError(null);
    setRes(null);
    try {
      const att: unknown = JSON.parse(text);
      setRes(await postJson<VerifyResult>("/api/attestation/verify", att));
    } catch (err) {
      setError(err instanceof SyntaxError ? "Invalid JSON" : errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function lookupMemo() {
    setError(null);
    setMemo(null);
    setThread(null);
    const id = tx.trim();
    try {
      setMemo(await getJson<MemoResult>(`/api/memo/${encodeURIComponent(id)}`));
      // Provenance thread is best-effort — a memo can exist without a reply chain.
      try {
        setThread(await getJson<ThreadResult>(`/api/memo/${encodeURIComponent(id)}/thread`));
      } catch {
        setThread(null);
      }
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function lookupCircle() {
    setCircleBusy(true);
    setCircle(null);
    try {
      setCircle(await getJson<CircleResult>(`/api/circle/transaction/${encodeURIComponent(circleId.trim())}`));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setCircleBusy(false);
    }
  }

  // Pretty-print whatever is in the box for the proof viewer.
  const proofView = useMemo(() => {
    if (!text.trim()) return PLACEHOLDER;
    try {
      return JSON.stringify(JSON.parse(text), null, 2);
    } catch {
      return text;
    }
  }, [text]);

  const verdict = res ? (res.verified ? "VALIDATED" : "REJECTED") : "AWAITING";
  const verdictColor = res
    ? res.verified
      ? "text-secondary-fixed-dim"
      : "text-error"
    : "text-on-surface-variant";
  // Gauge fill: full ring on verified, partial on rejected, empty while idle.
  const ringPct = res ? (res.verified ? 100 : 18) : 0;
  const circumference = 2 * Math.PI * 88;

  return (
    <main className="cyber-grid mx-auto min-h-screen max-w-container-max px-gutter pb-12 pt-24">
      {/* Hero + input */}
      <section className="mb-12">
        <div className="max-w-3xl">
          <h1 className="mb-4 font-display-lg text-display-lg text-on-surface">Cryptographic Audit</h1>
          <p className="mb-8 max-w-2xl text-on-surface-variant">
            Verify the integrity of any attestation from an <code className="text-primary-fixed-dim">/ask</code>{" "}
            response. Don&apos;t trust us — paste the proof object and check the chain-bound signature
            yourself.
          </p>
          <div className="group relative">
            <div className="absolute -inset-1 rounded-lg bg-gradient-to-r from-primary-fixed-dim/20 to-secondary-fixed-dim/20 opacity-25 blur transition duration-1000 group-focus-within:opacity-75" />
            <div className="relative flex flex-col overflow-hidden rounded-lg border border-outline-variant/50 bg-surface-container-lowest shadow-2xl transition-colors focus-within:border-primary-fixed-dim">
              <textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder={PLACEHOLDER}
                className="h-40 w-full resize-none border-none bg-transparent px-4 py-4 font-mono-data text-mono-data text-on-surface placeholder:text-outline focus:outline-none focus:ring-0"
              />
              <div className="flex justify-end border-t border-white/5 p-2">
                <button
                  type="button"
                  onClick={verify}
                  disabled={busy || !text.trim()}
                  className="bg-primary-fixed-dim px-8 py-3 font-label-caps text-label-caps font-bold text-on-primary-fixed transition-colors hover:brightness-110 disabled:opacity-50"
                >
                  {busy ? "VERIFYING…" : "VERIFY"}
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>

      {error && (
        <p className="mb-6 rounded-lg border border-error/30 bg-error-container/20 p-4 text-error">
          {error}
        </p>
      )}

      {/* Bento grid */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        {/* Proof object */}
        <div className="space-y-6 lg:col-span-8">
          <div className="glass-card relative overflow-hidden p-6">
            <div className="mb-6 flex items-start justify-between">
              <div>
                <h2 className="font-headline-md text-headline-md text-on-surface">Cryptographic Proof Object</h2>
                <p className="mt-1 font-label-caps text-[11px] text-on-surface-variant">
                  {res ? `AGENT ${res.agent_pubkey.slice(0, 18)}…` : "PASTE AN ATTESTATION ABOVE"}
                </p>
              </div>
              <div className="flex gap-2">
                <Copy text={proofView} label="⧉" />
              </div>
            </div>
            <div className="custom-scrollbar h-[400px] overflow-y-auto rounded border border-white/5 bg-black/50 p-4 font-mono-data text-mono-data leading-relaxed text-secondary-fixed-dim/90">
              <pre className="whitespace-pre-wrap break-all">{proofView}</pre>
            </div>
            {res && (
              <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-2">
                <div className="rounded border border-white/5 bg-surface-container-low p-4">
                  <span className="mb-1 block font-label-caps text-[10px] text-on-surface-variant">AGENT PUBKEY</span>
                  <span className="break-all font-mono-data text-sm text-on-surface">{res.agent_pubkey}</span>
                </div>
                <div className="rounded border border-white/5 bg-surface-container-low p-4">
                  <span className="mb-1 block font-label-caps text-[10px] text-on-surface-variant">QUERY HASH</span>
                  <span className="break-all font-mono-data text-sm text-on-surface">{res.query_hash}</span>
                </div>
              </div>
            )}
          </div>

          {/* Memo lookup — deep provenance */}
          <div className="glass-card overflow-hidden p-8">
            <span className="mb-4 inline-block rounded bg-primary-container/20 px-2 py-1 font-label-caps text-[10px] text-primary-container">
              DEEP PROVENANCE
            </span>
            <h2 className="mb-3 font-headline-md text-headline-md text-on-surface">Memo Lookup</h2>
            <p className="mb-6 text-on-surface-variant">
              Read the provenance memo bound to any settlement — the recorded reason a payment was made,
              traceable back to its on-chain transaction.
            </p>
            <div className="flex flex-col gap-2 sm:flex-row">
              <input
                value={tx}
                onChange={(e) => setTx(e.target.value)}
                placeholder="0x tx hash"
                className="flex-1 rounded border border-outline-variant/50 bg-surface-container-lowest px-3 py-2 font-mono-data text-mono-data text-on-surface placeholder:text-outline focus:border-primary-fixed-dim focus:outline-none focus:ring-0"
              />
              <button
                type="button"
                onClick={lookupMemo}
                disabled={!tx.trim()}
                className="rounded bg-secondary-fixed-dim px-6 py-2 font-label-caps text-label-caps font-bold text-on-secondary-fixed transition-all hover:brightness-110 disabled:opacity-40"
              >
                LOOK UP
              </button>
            </div>
            {memo && (
              <p className="mt-4 rounded border border-white/5 bg-surface-container-low p-3 text-sm text-on-surface">
                {memo.found ? memo.memo : <span className="text-outline">no memo for this tx</span>}
              </p>
            )}

            {/* Provenance thread — the chain a payment belongs to (e.g. refund → original send) */}
            {thread && (thread.ancestors.length > 0 || thread.replies.length > 0) && (
              <div className="mt-4">
                <p className="mb-2 font-label-caps text-[10px] text-on-surface-variant">PROVENANCE THREAD</p>
                <div className="space-y-1.5">
                  {[...thread.ancestors].reverse().map((it) => (
                    <ThreadRow key={it.tx_hash} item={it} label="replies to" />
                  ))}
                  <ThreadRow item={{ tx_hash: tx.trim(), memo: memo?.memo ?? null }} label="this" current />
                  {thread.replies.map((it) => (
                    <ThreadRow key={it.tx_hash} item={it} label="reply" />
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Circle W3S transaction lookup — opt-in tracking of wallet-provisioned txs */}
          <div className="glass-card p-8">
            <span className="mb-4 inline-block rounded bg-tertiary-fixed-dim/15 px-2 py-1 font-label-caps text-[10px] text-tertiary-fixed-dim">
              CIRCLE W3S
            </span>
            <h2 className="mb-3 font-headline-md text-headline-md text-on-surface">Transaction Status</h2>
            <p className="mb-6 text-on-surface-variant">
              Track a wallet-provisioned transaction submitted through Circle (e.g. an ERC-8004 register
              or ERC-8183 fund). Opt-in — needs <code className="text-primary-fixed-dim">KERYX_CIRCLE_API_KEY</code>.
            </p>
            <div className="flex flex-col gap-2 sm:flex-row">
              <input
                value={circleId}
                onChange={(e) => setCircleId(e.target.value)}
                placeholder="Circle transaction id"
                className="flex-1 rounded border border-outline-variant/50 bg-surface-container-lowest px-3 py-2 font-mono-data text-mono-data text-on-surface placeholder:text-outline focus:border-primary-fixed-dim focus:outline-none focus:ring-0"
              />
              <button
                type="button"
                onClick={lookupCircle}
                disabled={circleBusy || !circleId.trim()}
                className="rounded bg-primary-fixed-dim px-6 py-2 font-label-caps text-label-caps font-bold text-on-primary-fixed transition-all hover:brightness-110 disabled:opacity-40"
              >
                {circleBusy ? "CHECKING…" : "TRACK"}
              </button>
            </div>
            {circle && (
              <div className="mt-4 rounded border border-white/5 bg-surface-container-low p-3 text-sm">
                {!circle.enabled ? (
                  <span className="flex items-center gap-2 text-on-surface-variant">
                    <span className="material-symbols-outlined text-[16px] text-outline">toggle_off</span>
                    Circle tracking is disabled on this agent.
                  </span>
                ) : circle.error ? (
                  <span className="text-error">Lookup failed: {circle.error}</span>
                ) : (
                  <pre className="custom-scrollbar max-h-48 overflow-auto whitespace-pre-wrap break-all font-mono-data text-xs text-secondary-fixed-dim/90">
                    {JSON.stringify(circle.transaction, null, 2)}
                  </pre>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Verdict + live audits */}
        <div className="space-y-6 lg:col-span-4">
          <div className="glass-card flex flex-col items-center p-6 text-center">
            <h3 className="mb-6 font-label-caps text-label-caps text-on-surface-variant">VERIFICATION VERDICT</h3>
            <div className="relative mb-6 h-48 w-48">
              <svg className="h-full w-full -rotate-90">
                <circle
                  className="text-surface-variant"
                  cx="96"
                  cy="96"
                  fill="transparent"
                  r="88"
                  stroke="currentColor"
                  strokeWidth="8"
                />
                <circle
                  className={res?.verified ? "text-secondary-fixed-dim" : "text-error"}
                  cx="96"
                  cy="96"
                  fill="transparent"
                  r="88"
                  stroke="currentColor"
                  strokeWidth="8"
                  strokeDasharray={circumference}
                  strokeDashoffset={circumference * (1 - ringPct / 100)}
                  style={{ transition: "stroke-dashoffset 1s ease-out" }}
                />
              </svg>
              <div className="absolute inset-0 flex rotate-90 flex-col items-center justify-center">
                <span className="material-symbols-outlined icon-fill rotate-[-90deg] text-5xl text-on-surface">
                  {res ? (res.verified ? "verified" : "gpp_bad") : "pending"}
                </span>
              </div>
            </div>
            <p className={`font-mono-data text-lg ${verdictColor}`}>{verdict}</p>
            {res && (
              <p className="mt-1 font-label-caps text-[10px] text-on-surface-variant">
                {res.citations} citations bound
              </p>
            )}
            <p className="mt-4 px-4 text-sm text-on-surface-variant">
              The signature is checked against the agent&apos;s public key — proving the answer and its
              citations were not tampered with.
            </p>
          </div>

          {/* Live network audits = recent memos */}
          <div className="glass-card h-fit p-6">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="font-label-caps text-label-caps text-on-surface">RECENT PROVENANCE MEMOS</h3>
              <span className="h-2 w-2 animate-pulse rounded-full bg-secondary-fixed-dim" />
            </div>
            {feed.length === 0 && (
              <p className="font-label-caps text-[10px] text-outline">no memos recorded yet</p>
            )}
            <div className="space-y-4">
              {feed.slice(0, 6).map((m) => (
                <div key={m.tx_hash} className="group">
                  <div className="mb-1 flex items-center justify-between gap-2">
                    <a
                      href={ARC_EXPLORER_TX + m.tx_hash}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-mono-data text-xs text-primary-fixed-dim group-hover:underline"
                    >
                      {m.tx_hash.slice(0, 12)}…
                    </a>
                    <span className="font-label-caps text-[9px] text-secondary-fixed-dim">RECORDED</span>
                  </div>
                  <p className="truncate text-[11px] text-on-surface-variant" title={m.memo}>
                    {m.memo}
                  </p>
                </div>
              ))}
            </div>
            {feed.length > 0 && (
              <a
                href="/ledger"
                className="mt-6 block w-full rounded border border-white/10 py-2 text-center font-label-caps text-[10px] text-on-surface-variant transition-colors hover:bg-white/5"
              >
                VIEW FULL LEDGER
              </a>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}

function ThreadRow({
  item,
  label,
  current = false,
}: {
  item: ThreadItem;
  label: string;
  current?: boolean;
}) {
  return (
    <div
      className={`flex items-center gap-2 rounded border px-3 py-2 ${
        current
          ? "border-primary-fixed-dim/40 bg-primary-fixed-dim/10"
          : "border-white/5 bg-surface-container-lowest"
      }`}
    >
      <span className="w-16 shrink-0 font-label-caps text-[9px] uppercase text-on-surface-variant">{label}</span>
      {item.meta?.kind && (
        <span className="shrink-0 rounded bg-white/5 px-1.5 py-0.5 font-mono-data text-[9px] uppercase text-tertiary-fixed-dim">
          {item.meta.kind}
        </span>
      )}
      <span className="min-w-0 flex-1 truncate text-xs text-on-surface" title={item.memo ?? ""}>
        {item.memo ?? "—"}
      </span>
      <a
        href={ARC_EXPLORER_TX + item.tx_hash}
        target="_blank"
        rel="noopener noreferrer"
        className="shrink-0 font-mono-data text-[10px] text-primary-fixed-dim hover:underline"
      >
        {item.tx_hash.slice(0, 8)}…
      </a>
    </div>
  );
}
