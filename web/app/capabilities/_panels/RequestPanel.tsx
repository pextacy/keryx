"use client";

import { useState } from "react";
import { errorMessage, getJson, postJson } from "@/lib/api";
import type { RequestResponse } from "@/lib/capabilities";
import { useToast } from "@/app/Toast";
import { Copy } from "@/app/Copy";
import { Card, ErrorNote, Field } from "./Card";
import { TxLink } from "./TxLink";

// Split-bill money request (ported from arc-p2p-payments "request money"): a payee asks a
// set of payers to cover a total, split dust-free. Each payer fulfils their share, which
// settles to the payee. Shows collected vs outstanding and per-payer paid/pending state.
export function RequestPanel() {
  const { toast, notify } = useToast();
  const [payee, setPayee] = useState("0x" + "e".repeat(40));
  const [payers, setPayers] = useState("0x" + "a".repeat(40) + "\n0x" + "b".repeat(40));
  const [total, setTotal] = useState("0.10");
  const [req, setReq] = useState<RequestResponse | null>(null);
  const [lookupId, setLookupId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function lookup() {
    const id = lookupId.trim();
    if (!id) return;
    setError(null);
    try {
      const r = await getJson<RequestResponse>(`/api/request/${encodeURIComponent(id)}`);
      if (r.found === false) setError(`no request ${id}`);
      else setReq(r);
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function create() {
    setBusy(true);
    setError(null);
    try {
      const list = payers
        .split(/\s+/)
        .map((p) => p.trim())
        .filter(Boolean);
      const r = await postJson<RequestResponse>("/api/request", { payee, payers: list, total });
      if (r.error) {
        setError(r.error);
        setReq(null);
      } else {
        setReq(r);
      }
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function fulfil(payer: string) {
    if (!req) return;
    setError(null);
    try {
      const r = await postJson<RequestResponse>(`/api/request/${req.id}/fulfil`, { payer });
      if (r.error) setError(r.error);
      else {
        setReq(r);
        if (r.settled) notify("Share fulfilled", r.tx_hash);
      }
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  const pct =
    req && Number(req.total) > 0 ? (Number(req.collected) / Number(req.total)) * 100 : 0;
  const settled = req?.status === "settled";

  return (
    <Card
      title="Split-bill request (P2P)"
      subtitle="A payee requests a total split across payers — each fulfils their share"
    >
      {!req ? (
        <>
          <Field label="Payee (receives funds)">
            <input
              value={payee}
              onChange={(e) => setPayee(e.target.value)}
              className="w-full rounded border border-outline-variant/40 bg-surface-container-lowest text-on-surface placeholder:text-outline px-2 py-1 font-mono text-xs"
            />
          </Field>
          <div className="mt-2">
            <Field label="Payers (one 0x wallet per line)">
              <textarea
                value={payers}
                onChange={(e) => setPayers(e.target.value)}
                rows={3}
                className="w-full rounded border border-outline-variant/40 bg-surface-container-lowest text-on-surface placeholder:text-outline px-2 py-1 font-mono text-xs"
              />
            </Field>
          </div>
          <div className="mt-2">
            <Field label="Total (USDC)">
              <input
                value={total}
                onChange={(e) => setTotal(e.target.value)}
                className="w-28 rounded border border-outline-variant/40 bg-surface-container-lowest text-on-surface placeholder:text-outline px-2 py-1 font-mono"
              />
            </Field>
          </div>
          <button
            type="button"
            onClick={() => void create()}
            disabled={busy}
            className="mt-4 rounded bg-primary-fixed-dim px-4 py-2 text-sm text-on-primary-fixed font-bold disabled:opacity-50"
          >
            {busy ? "Creating…" : "Create request"}
          </button>

          <div className="mt-4 border-t pt-3">
            <Field label="…or open a shared request by id">
              <div className="flex gap-2">
                <input
                  value={lookupId}
                  onChange={(e) => setLookupId(e.target.value)}
                  placeholder="req-1"
                  className="w-28 rounded border border-outline-variant/40 bg-surface-container-lowest text-on-surface placeholder:text-outline px-2 py-1 font-mono text-sm"
                />
                <button
                  type="button"
                  onClick={() => void lookup()}
                  className="rounded border px-3 py-1.5 text-sm"
                >
                  Open
                </button>
              </div>
            </Field>
          </div>
        </>
      ) : (
        <>
          <div className="flex items-center justify-between text-sm">
            <span className="flex items-center gap-1">
              <span className="font-mono text-on-surface-variant">{req.id}</span>
              <Copy text={req.id} label="share" />
            </span>
            <span
              className={`rounded px-2 py-0.5 text-xs font-medium ${
                settled ? "bg-secondary-fixed-dim/10 text-secondary-fixed-dim" : "bg-error-container/20 text-error"
              }`}
            >
              {req.status}
            </span>
          </div>

          <div className="mt-2">
            <div className="flex justify-between text-xs text-on-surface-variant">
              <span>collected {req.collected}</span>
              <span>of {req.total} USDC</span>
            </div>
            <div className="mt-1 h-1.5 w-full overflow-hidden rounded bg-white/5">
              <div
                className="h-full rounded bg-secondary-fixed-dim"
                style={{ width: `${Math.min(100, pct)}%` }}
              />
            </div>
          </div>

          <ul className="mt-4 space-y-2 text-sm">
            {req.shares?.map((s) => (
              <li key={s.payer} className="flex items-center justify-between gap-2 font-mono text-xs">
                <span className="truncate text-on-surface-variant" title={s.payer}>
                  {s.payer.slice(0, 12)}…
                </span>
                <span className="flex items-center gap-2">
                  <span className="text-secondary-fixed-dim">{s.amount}</span>
                  {s.paid ? (
                    s.tx_hash ? (
                      <TxLink hash={s.tx_hash} prefix="paid" />
                    ) : (
                      <span className="text-secondary-fixed-dim">paid ✓</span>
                    )
                  ) : (
                    <button
                      type="button"
                      onClick={() => void fulfil(s.payer)}
                      className="rounded border border-outline-variant/40 bg-surface-container-lowest text-on-surface placeholder:text-outline px-2 py-0.5 text-on-surface hover:bg-white/5"
                    >
                      Fulfil
                    </button>
                  )}
                </span>
              </li>
            ))}
          </ul>

          <button
            type="button"
            onClick={() => {
              setReq(null);
              setError(null);
            }}
            className="mt-4 rounded border px-3 py-1.5 text-sm"
          >
            New request
          </button>
        </>
      )}

      <ErrorNote message={error} />
      {toast}
    </Card>
  );
}
