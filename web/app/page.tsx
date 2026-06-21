"use client";

import { useState } from "react";
import { ARC_EXPLORER_TX, type AskResponse } from "@/lib/types";

export default function Home() {
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
    <main className="mx-auto max-w-3xl p-8">
      <h1 className="text-3xl font-semibold">Keryx</h1>
      <p className="mt-1 text-gray-500">
        Ask a question. Watch the agent pay every source it genuinely cites — live on Arc.
      </p>

      <form onSubmit={ask} className="mt-6 flex gap-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="flex-1 rounded border border-gray-300 px-3 py-2"
          placeholder="Ask anything…"
        />
        <button
          type="submit"
          disabled={loading}
          className="rounded bg-black px-4 py-2 text-white disabled:opacity-50"
        >
          {loading ? "Researching…" : "Ask"}
        </button>
      </form>

      {error && <p className="mt-4 rounded bg-red-50 p-3 text-red-700">{error}</p>}

      {res && (
        <section className="mt-8 space-y-6">
          <div>
            <h2 className="text-lg font-medium">Answer</h2>
            <p className="mt-2 whitespace-pre-wrap text-gray-800">{res.answer}</p>
          </div>

          <div className="rounded border border-gray-200 p-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-medium">Settlement</h2>
              <span className="font-mono text-green-700">{res.total_settled} USDC</span>
            </div>

            <h3 className="mt-3 text-sm font-semibold text-gray-700">
              Cited &amp; paid ({cited.length})
            </h3>
            <ul className="mt-1 space-y-1">
              {cited.map((c) => (
                <li key={c.source_url} className="flex items-center justify-between text-sm">
                  <a href={c.source_url} className="text-blue-600 underline" target="_blank">
                    {c.source_url}
                  </a>
                  <span className="flex items-center gap-3 font-mono">
                    <span title="grounding score">g={c.g.toFixed(2)}</span>
                    <span className="text-green-700">{c.amount} USDC</span>
                    {c.tx_hash && (
                      <a
                        href={ARC_EXPLORER_TX + c.tx_hash}
                        target="_blank"
                        className="text-blue-600 underline"
                      >
                        tx
                      </a>
                    )}
                    {c.author_wallet &&
                      (tipped[c.source_url] ? (
                        <a
                          href={ARC_EXPLORER_TX + tipped[c.source_url]}
                          target="_blank"
                          className="text-purple-600 underline"
                        >
                          tipped ✓
                        </a>
                      ) : (
                        <button
                          type="button"
                          onClick={() => tip(c.source_url, c.author_wallet as string)}
                          className="rounded border border-purple-300 px-1.5 text-xs text-purple-700"
                        >
                          tip $0.001
                        </button>
                      ))}
                  </span>
                </li>
              ))}
            </ul>

            <h3 className="mt-4 text-sm font-semibold text-gray-500">
              Evaluated, not cited ({skipped.length}) — proves we pay on citation, not fetch
            </h3>
            <ul className="mt-1 space-y-1">
              {skipped.map((c) => (
                <li
                  key={c.source_url}
                  className="flex items-center justify-between text-sm text-gray-400"
                >
                  <span>{c.source_url}</span>
                  <span className="font-mono">
                    g={c.g.toFixed(2)} · $0
                  </span>
                </li>
              ))}
            </ul>
          </div>

          <div className="rounded border border-gray-200 p-4 text-sm">
            <div className="flex items-center justify-between">
              <h2 className="font-medium">Attestation</h2>
              <span
                className={
                  res.attestation.verified ? "text-green-700" : "text-red-600"
                }
              >
                {res.attestation.verified ? "✓ signature verified" : "✗ invalid"}
              </span>
            </div>
            <dl className="mt-2 space-y-1 font-mono text-xs text-gray-600">
              <div>agent: {res.attestation.agent_pubkey}</div>
              <div>query_hash: {res.attestation.query_hash}</div>
              <div>answer_hash: {res.attestation.answer_hash}</div>
            </dl>
          </div>
        </section>
      )}
    </main>
  );
}
