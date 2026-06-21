"use client";

import { useState } from "react";
import { errorMessage, postJson } from "@/lib/api";

interface VerifyResult {
  verified: boolean;
  agent_pubkey: string;
  query_hash: string;
  citations: number;
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
    </main>
  );
}
