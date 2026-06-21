"use client";

import { useState } from "react";
import { errorMessage, postJson } from "@/lib/api";
import { ARC_EXPLORER_TX } from "@/lib/types";
import type { SendResponse } from "@/lib/capabilities";
import { Card, ErrorNote, Field } from "./Card";

export function SendPanel() {
  const [to, setTo] = useState("0x" + "a".repeat(40));
  const [amount, setAmount] = useState("0.01");
  const [memo, setMemo] = useState("grounded: https://example.com/post");
  const [res, setRes] = useState<SendResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      setRes(await postJson<SendResponse>("/api/send", { to, amount, memo }));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="Send with memo" subtitle="A transfer whose memo carries why it was paid (provenance)">
      <Field label="To (0x wallet)">
        <input
          value={to}
          onChange={(e) => setTo(e.target.value)}
          className="w-full rounded border border-gray-300 px-2 py-1 font-mono text-xs"
        />
      </Field>
      <div className="mt-2">
        <Field label="Amount (USDC)">
          <input
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            className="w-32 rounded border border-gray-300 px-2 py-1 font-mono"
          />
        </Field>
      </div>
      <div className="mt-2">
        <Field label="Memo (provenance)">
          <input
            value={memo}
            onChange={(e) => setMemo(e.target.value)}
            className="w-full rounded border border-gray-300 px-2 py-1 text-sm"
            placeholder="citation URL, attestation hash, job id…"
          />
        </Field>
      </div>

      <button
        type="button"
        onClick={submit}
        disabled={busy}
        className="mt-4 rounded bg-black px-4 py-2 text-white disabled:opacity-50"
      >
        {busy ? "Sending…" : "Send"}
      </button>

      <ErrorNote message={error} />

      {res && (
        <dl className="mt-4 space-y-1 font-mono text-sm">
          <div className="flex justify-between">
            <span className="text-gray-500">amount</span>
            <span className="text-green-700">{res.amount} USDC</span>
          </div>
          <div className="truncate text-gray-600">memo: {res.memo}</div>
          {res.tx_hash && (
            <a href={ARC_EXPLORER_TX + res.tx_hash} target="_blank" className="text-blue-600 underline">
              tx {res.tx_hash.slice(0, 14)}…
            </a>
          )}
        </dl>
      )}
    </Card>
  );
}
