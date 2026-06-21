"use client";

import { useState } from "react";
import { errorMessage, postJson } from "@/lib/api";
import { ARC_EXPLORER_TX } from "@/lib/types";
import type { SendResponse } from "@/lib/capabilities";
import { Copy } from "@/app/Copy";
import { useToast } from "@/app/Toast";
import { Card, ErrorNote, Field } from "./Card";

export function SendPanel() {
  const { toast, notify } = useToast();
  const [to, setTo] = useState("0x" + "a".repeat(40));
  const [amount, setAmount] = useState("0.01");
  const [memo, setMemo] = useState("grounded g=0.91");
  const [kind, setKind] = useState("citation");
  const [ref, setRef] = useState("https://example.com/post");
  const [confidential, setConfidential] = useState(false);
  const [attachmentUrl, setAttachmentUrl] = useState("");
  const [refundTo, setRefundTo] = useState("0x" + "9".repeat(40));
  const [res, setRes] = useState<SendResponse | null>(null);
  const [refunded, setRefunded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit() {
    setBusy(true);
    setError(null);
    setRefunded(false);
    try {
      const r = await postJson<SendResponse>("/api/send", {
        to,
        amount,
        memo,
        kind,
        ref,
        confidential,
        attachment_url: attachmentUrl,
        refund_to: refundTo,
      });
      setRes(r);
      if (r.settled) notify(`Sent ${r.amount} USDC`, r.tx_hash);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function refund() {
    if (!res?.tx_hash) return;
    try {
      const r = await postJson<{ refunded: boolean }>(`/api/refund/${res.tx_hash}`, {
        reason: "requested",
      });
      setRefunded(Boolean(r.refunded));
    } catch (err) {
      setError(errorMessage(err));
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
      <div className="mt-2 flex gap-2">
        <Field label="Kind (recibo)">
          <select
            value={kind}
            onChange={(e) => setKind(e.target.value)}
            className="rounded border border-gray-300 px-2 py-1 text-sm"
          >
            {["citation", "invoice", "attestation", "authorization", "job", "note", "other"].map((k) => (
              <option key={k}>{k}</option>
            ))}
          </select>
        </Field>
        <Field label="Ref (URL / hash / id)">
          <input
            value={ref}
            onChange={(e) => setRef(e.target.value)}
            className="w-full rounded border border-gray-300 px-2 py-1 font-mono text-xs"
          />
        </Field>
      </div>
      <label className="mt-2 flex items-center gap-2 text-xs text-gray-600">
        <input
          type="checkbox"
          checked={confidential}
          onChange={(e) => setConfidential(e.target.checked)}
        />
        Confidential memo (note redacted in the public feed — recibo encrypted scheme)
      </label>
      <div className="mt-2">
        <Field label="Attachment URL (recibo mime'd payload, optional)">
          <input
            value={attachmentUrl}
            onChange={(e) => setAttachmentUrl(e.target.value)}
            placeholder="https://…/receipt.png"
            className="w-full rounded border border-gray-300 px-2 py-1 font-mono text-xs"
          />
        </Field>
      </div>
      <div className="mt-2">
        <Field label="Refund to (bound at send — refund-protocol)">
          <input
            value={refundTo}
            onChange={(e) => setRefundTo(e.target.value)}
            className="w-full rounded border border-gray-300 px-2 py-1 font-mono text-xs"
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
          {res.tx_hash &&
            (refunded ? (
              <span className="text-purple-700">refunded ✓</span>
            ) : (
              <button
                type="button"
                onClick={() => void refund()}
                className="self-start rounded border border-purple-300 px-2 py-0.5 text-xs text-purple-700"
              >
                refund (dispute)
              </button>
            ))}
        </dl>
      )}
      {toast}
    </Card>
  );
}
