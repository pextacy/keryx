"use client";

import { useEffect, useState } from "react";
import { errorMessage, getJson, postJson } from "@/lib/api";
import { ARC_EXPLORER_TX } from "@/lib/types";

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

const PLACEHOLDER = `{
  "query_hash": "…",
  "answer_hash": "…",
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
  const [feed, setFeed] = useState<MemoItem[]>([]);

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
    try {
      setMemo(await getJson<MemoResult>(`/api/memo/${encodeURIComponent(tx.trim())}`));
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <main className="mx-auto max-w-3xl p-8">
      <h1 className="text-3xl font-semibold">Attestation audit</h1>
      <p className="mt-1 text-gray-500">
        Paste an attestation (from an <code>/ask</code> response) and verify its signature
        independently — don&apos;t trust us, check the chain-bound signature yourself.
      </p>

      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={PLACEHOLDER}
        className="mt-6 h-64 w-full rounded border border-gray-300 p-3 font-mono text-xs"
      />
      <button
        type="button"
        onClick={verify}
        disabled={busy || !text.trim()}
        className="mt-3 rounded bg-black px-4 py-2 text-white disabled:opacity-50"
      >
        {busy ? "Verifying…" : "Verify signature"}
      </button>

      {error && <p className="mt-4 rounded bg-red-50 p-3 text-red-700">{error}</p>}

      {res && (
        <div className="mt-6 rounded border border-gray-200 p-4">
          <span className={res.verified ? "text-lg text-green-700" : "text-lg text-red-600"}>
            {res.verified ? "✓ signature verified" : "✗ invalid signature"}
          </span>
          <dl className="mt-2 space-y-1 font-mono text-xs text-gray-600">
            <div>agent: {res.agent_pubkey}</div>
            <div>query_hash: {res.query_hash}</div>
            <div>citations: {res.citations}</div>
          </dl>
        </div>
      )}

      <h2 className="mt-10 text-lg font-medium">Memo lookup</h2>
      <p className="mt-1 text-sm text-gray-500">
        Read the provenance memo bound to a settlement (why a payment was made).
      </p>
      <div className="mt-3 flex gap-2">
        <input
          value={tx}
          onChange={(e) => setTx(e.target.value)}
          placeholder="0x tx hash"
          className="flex-1 rounded border border-gray-300 px-3 py-2 font-mono text-xs"
        />
        <button
          type="button"
          onClick={lookupMemo}
          disabled={!tx.trim()}
          className="rounded border px-4 py-2 disabled:opacity-40"
        >
          Look up
        </button>
      </div>
      {memo && (
        <p className="mt-3 rounded border border-gray-200 p-3 text-sm">
          {memo.found ? memo.memo : <span className="text-gray-400">no memo for this tx</span>}
        </p>
      )}

      {feed.length > 0 && (
        <>
          <h2 className="mt-10 text-lg font-medium">Recent memos</h2>
          <ul className="mt-2 space-y-1 text-sm">
            {feed.map((m) => (
              <li key={m.tx_hash} className="flex items-center justify-between gap-3">
                <span className="truncate">{m.memo}</span>
                <a
                  href={ARC_EXPLORER_TX + m.tx_hash}
                  target="_blank"
                  className="shrink-0 font-mono text-xs text-blue-600 underline"
                >
                  {m.tx_hash.slice(0, 10)}…
                </a>
              </li>
            ))}
          </ul>
        </>
      )}
    </main>
  );
}
