"use client";

import { useState } from "react";
import { errorMessage, postJson } from "@/lib/api";
import { ARC_EXPLORER_TX } from "@/lib/types";
import type { SwapResponse } from "@/lib/capabilities";
import { Copy } from "@/app/Copy";
import { useToast } from "@/app/Toast";
import { Card, ErrorNote, Field } from "./Card";

const TOKENS = ["USDC", "EURC"] as const;

// Port of circlefin/arc-stablecoin-fx's swap panel: a quote (estimateSwap) then an
// execute (kit.swap()). Here both hit the agent's offline FX engine — no funds needed.
export function SwapPanel() {
  const { toast, notify } = useToast();
  const [tokenIn, setTokenIn] = useState<(typeof TOKENS)[number]>("USDC");
  const [tokenOut, setTokenOut] = useState<(typeof TOKENS)[number]>("EURC");
  const [amountIn, setAmountIn] = useState("10");
  const [quote, setQuote] = useState<SwapResponse | null>(null);
  const [res, setRes] = useState<SwapResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function flip() {
    setTokenIn(tokenOut);
    setTokenOut(tokenIn);
    setQuote(null);
    setRes(null);
  }

  async function run<T extends SwapResponse>(path: string, set: (v: T | null) => void) {
    setBusy(true);
    setError(null);
    try {
      const r = await postJson<T>(path, {
        token_in: tokenIn,
        token_out: tokenOut,
        amount_in: amountIn,
      });
      if (r.error) {
        setError(r.error);
        set(null);
      } else {
        set(r);
        if (r.settled) notify(`Swapped to ${r.amount_out} ${r.token_out}`, r.tx_hash);
      }
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card
      title="Stablecoin swap (USDC ↔ EURC)"
      subtitle="Quote then swap an author payout across stablecoins (App Kit FX, offline engine)"
    >
      <div className="flex items-end gap-2">
        <Field label="From">
          <select
            value={tokenIn}
            onChange={(e) => setTokenIn(e.target.value as (typeof TOKENS)[number])}
            className="rounded border border-gray-300 px-2 py-1 font-mono text-sm"
          >
            {TOKENS.map((t) => (
              <option key={t}>{t}</option>
            ))}
          </select>
        </Field>
        <button
          type="button"
          onClick={flip}
          title="Flip direction"
          className="mb-1 rounded border px-2 py-1 text-sm"
        >
          ⇄
        </button>
        <Field label="To">
          <select
            value={tokenOut}
            onChange={(e) => setTokenOut(e.target.value as (typeof TOKENS)[number])}
            className="rounded border border-gray-300 px-2 py-1 font-mono text-sm"
          >
            {TOKENS.map((t) => (
              <option key={t}>{t}</option>
            ))}
          </select>
        </Field>
      </div>

      <div className="mt-2">
        <Field label={`Amount (${tokenIn})`}>
          <input
            value={amountIn}
            onChange={(e) => setAmountIn(e.target.value)}
            className="w-32 rounded border border-gray-300 px-2 py-1 font-mono"
          />
        </Field>
      </div>

      <div className="mt-4 flex gap-2">
        <button
          type="button"
          onClick={() => void run<SwapResponse>("/api/swap/quote", setQuote)}
          disabled={busy || tokenIn === tokenOut}
          className="rounded border px-3 py-1.5 text-sm disabled:opacity-50"
        >
          Quote
        </button>
        <button
          type="button"
          onClick={() => void run<SwapResponse>("/api/swap", setRes)}
          disabled={busy || tokenIn === tokenOut}
          className="rounded bg-black px-3 py-1.5 text-sm text-white disabled:opacity-50"
        >
          {busy ? "…" : "Swap"}
        </button>
      </div>
      {tokenIn === tokenOut && (
        <p className="mt-2 text-xs text-amber-700">pick two different tokens</p>
      )}

      {quote && !res && (
        <dl className="mt-4 space-y-1 font-mono text-sm">
          <div className="flex justify-between">
            <span className="text-gray-500">you get</span>
            <span className="text-green-700">
              {quote.amount_out} {quote.token_out}
            </span>
          </div>
          <div className="flex justify-between text-xs text-gray-500">
            <span>rate</span>
            <span>{quote.effective_rate}</span>
          </div>
          <div className="flex justify-between text-xs text-gray-500">
            <span>app fee</span>
            <span>
              {quote.app_fee} {quote.token_out} ({quote.app_fee_bps} bps)
            </span>
          </div>
        </dl>
      )}

      {res && (
        <dl className="mt-4 space-y-1 font-mono text-sm">
          <div className="flex justify-between">
            <span className="text-gray-500">swapped</span>
            <span className="text-green-700">
              {res.amount_in} {res.token_in} → {res.amount_out} {res.token_out}
            </span>
          </div>
          {res.tx_hash && (
            <div className="flex items-center gap-1">
              <a
                href={ARC_EXPLORER_TX + res.tx_hash}
                target="_blank"
                className="text-blue-600 underline"
              >
                tx {res.tx_hash.slice(0, 14)}…
              </a>
              <Copy text={res.tx_hash} />
            </div>
          )}
        </dl>
      )}

      <ErrorNote message={error} />
      {toast}
    </Card>
  );
}
