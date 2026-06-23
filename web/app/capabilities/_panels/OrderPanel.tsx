"use client";

import { useState } from "react";
import { errorMessage, postJson } from "@/lib/api";
import type { OrderResponse } from "@/lib/capabilities";
import { useToast } from "@/app/Toast";
import { Card, ErrorNote, Field } from "./Card";
import { TxLink } from "./TxLink";

type ItemRow = { description: string; to: string; amount: string };

// Multi-item order (ported from arc-commerce checkout): bundle line-items paying different
// recipients into one order, settle them together at checkout.
export function OrderPanel() {
  const { toast, notify } = useToast();
  const [rows, setRows] = useState<ItemRow[]>([
    { description: "source author", to: "0x" + "a".repeat(40), amount: "0.003" },
    { description: "validator", to: "0x" + "b".repeat(40), amount: "0.002" },
  ]);
  const [order, setOrder] = useState<OrderResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const placed = order !== null;

  function update(i: number, patch: Partial<ItemRow>) {
    setRows((rs) => rs.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  }
  function addRow() {
    setRows((rs) => [...rs, { description: "line item", to: "0x" + "c".repeat(40), amount: "0.001" }]);
  }

  async function create() {
    setBusy(true);
    setError(null);
    try {
      const r = await postJson<OrderResponse>("/api/order", { items: rows });
      if (r.error) setError(r.error);
      else setOrder(r);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function checkout() {
    if (!order) return;
    setBusy(true);
    setError(null);
    try {
      const r = await postJson<OrderResponse>(`/api/order/${order.id}/checkout`, {});
      if (r.error) setError(r.error);
      else {
        setOrder(r);
        const firstTx = r.items?.find((i) => i.tx_hash)?.tx_hash ?? null;
        notify(`Order ${r.status} · ${r.paid} USDC`, firstTx);
      }
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card
      title="Order checkout (commerce)"
      subtitle="Bundle line-items paying different recipients, settle together at checkout"
    >
      {!placed ? (
        <>
          <div className="space-y-2">
            {rows.map((r, i) => (
              <div key={i} className="flex items-center gap-2">
                <input
                  value={r.description}
                  onChange={(e) => update(i, { description: e.target.value })}
                  className="flex-1 rounded border border-outline-variant/40 bg-surface-container-lowest text-on-surface placeholder:text-outline px-2 py-1 text-sm"
                />
                <input
                  value={r.to}
                  onChange={(e) => update(i, { to: e.target.value })}
                  className="w-28 rounded border border-outline-variant/40 bg-surface-container-lowest text-on-surface placeholder:text-outline px-2 py-1 font-mono text-[11px]"
                />
                <input
                  value={r.amount}
                  onChange={(e) => update(i, { amount: e.target.value })}
                  className="w-16 rounded border border-outline-variant/40 bg-surface-container-lowest text-on-surface placeholder:text-outline px-2 py-1 font-mono text-xs"
                />
              </div>
            ))}
          </div>
          <div className="mt-3 flex gap-2">
            <button type="button" onClick={addRow} className="rounded border px-3 py-1.5 text-sm">
              + Line
            </button>
            <button
              type="button"
              onClick={() => void create()}
              disabled={busy}
              className="rounded bg-primary-fixed-dim px-3 py-1.5 text-sm text-on-primary-fixed font-bold disabled:opacity-50"
            >
              {busy ? "…" : "Create order"}
            </button>
          </div>
        </>
      ) : (
        <>
          <div className="flex items-center justify-between text-sm">
            <span className="font-mono text-on-surface-variant">{order.id}</span>
            <span
              className={`rounded px-2 py-0.5 text-xs font-medium ${
                order.status === "paid"
                  ? "bg-secondary-fixed-dim/10 text-secondary-fixed-dim"
                  : order.status === "partial"
                    ? "bg-error-container/20 text-error"
                    : "bg-white/5 text-on-surface-variant"
              }`}
            >
              {order.status}
            </span>
          </div>
          <div className="mt-1 text-xs text-on-surface-variant">
            {order.paid} of {order.total} USDC settled
          </div>

          <ul className="mt-3 space-y-1.5">
            {order.items?.map((it, i) => (
              <li key={i} className="flex items-center justify-between gap-2 text-sm">
                <span className="truncate">{it.description}</span>
                <span className="flex items-center gap-2 font-mono text-xs">
                  <span className="text-secondary-fixed-dim">{it.amount}</span>
                  {it.tx_hash ? (
                    <TxLink hash={it.tx_hash} prefix="tx" chars={0} />
                  ) : (
                    <span className="text-outline">pending</span>
                  )}
                </span>
              </li>
            ))}
          </ul>

          {order.status === "pending" && (
            <button
              type="button"
              onClick={() => void checkout()}
              disabled={busy}
              className="mt-3 rounded bg-primary-fixed-dim px-3 py-1.5 text-sm text-on-primary-fixed font-bold disabled:opacity-50"
            >
              {busy ? "…" : "Checkout"}
            </button>
          )}
          <button
            type="button"
            onClick={() => {
              setOrder(null);
              setError(null);
            }}
            className="mt-3 ml-2 rounded border px-3 py-1.5 text-sm"
          >
            New order
          </button>
        </>
      )}

      <ErrorNote message={error} />
      {toast}
    </Card>
  );
}
