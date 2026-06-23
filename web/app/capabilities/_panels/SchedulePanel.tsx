"use client";

import { useState } from "react";
import { errorMessage, postJson } from "@/lib/api";
import type { ScheduleResponse } from "@/lib/capabilities";
import { useToast } from "@/app/Toast";
import { Card, ErrorNote, Field } from "./Card";
import { TxLink } from "./TxLink";

// Recurring payment schedule (ported from arc-fintech): a fixed amount paid per run for N runs
// — the discrete subscription/payroll counterpart to streaming. Advance each installment with
// "Run next".
export function SchedulePanel() {
  const { toast, notify } = useToast();
  const [payer, setPayer] = useState("0x" + "a".repeat(40));
  const [payee, setPayee] = useState("0x" + "b".repeat(40));
  const [amount, setAmount] = useState("0.002");
  const [runs, setRuns] = useState("3");
  const [sched, setSched] = useState<ScheduleResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function create() {
    setBusy(true);
    setError(null);
    try {
      const r = await postJson<ScheduleResponse>("/api/schedule", {
        payer,
        payee,
        amount,
        runs: Number(runs),
      });
      if (r.error) setError(r.error);
      else setSched(r);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function act(path: string, label?: string) {
    if (!sched) return;
    setBusy(true);
    setError(null);
    try {
      const r = await postJson<ScheduleResponse>(`/api/schedule/${sched.id}/${path}`, {});
      if (r.error) setError(r.error);
      else {
        setSched(r);
        if (label && r.ran) notify(label, r.tx_hash);
      }
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  const active = sched?.status === "active";

  return (
    <Card
      title="Recurring schedule (fintech)"
      subtitle="A fixed amount paid per run for N runs — subscription/payroll style"
    >
      {!sched ? (
        <>
          <div className="flex gap-2">
            <Field label="Payer">
              <input
                value={payer}
                onChange={(e) => setPayer(e.target.value)}
                className="w-full rounded border border-outline-variant/40 bg-surface-container-lowest text-on-surface placeholder:text-outline px-2 py-1 font-mono text-[11px]"
              />
            </Field>
            <Field label="Payee">
              <input
                value={payee}
                onChange={(e) => setPayee(e.target.value)}
                className="w-full rounded border border-outline-variant/40 bg-surface-container-lowest text-on-surface placeholder:text-outline px-2 py-1 font-mono text-[11px]"
              />
            </Field>
          </div>
          <div className="mt-2 flex items-end gap-2">
            <Field label="Per run (USDC)">
              <input
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                className="w-24 rounded border border-outline-variant/40 bg-surface-container-lowest text-on-surface placeholder:text-outline px-2 py-1 font-mono"
              />
            </Field>
            <Field label="Runs">
              <input
                value={runs}
                onChange={(e) => setRuns(e.target.value)}
                className="w-16 rounded border border-outline-variant/40 bg-surface-container-lowest text-on-surface placeholder:text-outline px-2 py-1 font-mono"
              />
            </Field>
            <button
              type="button"
              onClick={() => void create()}
              disabled={busy}
              className="mb-1 rounded bg-primary-fixed-dim px-3 py-1.5 text-sm text-on-primary-fixed font-bold disabled:opacity-50"
            >
              {busy ? "…" : "Create"}
            </button>
          </div>
        </>
      ) : (
        <>
          <div className="flex items-center justify-between text-sm">
            <span className="font-mono text-on-surface-variant">{sched.id}</span>
            <span
              className={`rounded px-2 py-0.5 text-xs font-medium ${
                sched.status === "completed"
                  ? "bg-secondary-fixed-dim/10 text-secondary-fixed-dim"
                  : sched.status === "cancelled"
                    ? "bg-surface-container-high text-on-surface-variant"
                    : "bg-error-container/20 text-error"
              }`}
            >
              {sched.status}
            </span>
          </div>
          <div className="mt-1 text-xs text-on-surface-variant">
            {sched.runs_done}/{sched.total_runs} runs · paid {sched.paid} · {sched.remaining} left
          </div>

          <div className="mt-2 flex gap-1">
            {Array.from({ length: sched.total_runs ?? 0 }).map((_, i) => (
              <span
                key={i}
                className={`h-2 flex-1 rounded ${
                  i < (sched.runs_done ?? 0) ? "bg-secondary-fixed-dim" : "bg-surface-container-high"
                }`}
              />
            ))}
          </div>

          {sched.tx_hashes && sched.tx_hashes.length > 0 && (
            <ul className="mt-2 space-y-0.5 text-xs">
              {sched.tx_hashes.map((tx, i) => (
                <li key={i} className="flex items-center gap-1 font-mono text-on-surface-variant">
                  run {i + 1}: <TxLink hash={tx} prefix="tx" />
                </li>
              ))}
            </ul>
          )}

          <div className="mt-3 flex gap-2">
            {active && (
              <button
                type="button"
                onClick={() => void act("run", "Installment paid")}
                disabled={busy}
                className="rounded bg-primary-fixed-dim px-3 py-1.5 text-sm text-on-primary-fixed font-bold disabled:opacity-50"
              >
                {busy ? "…" : "Run next"}
              </button>
            )}
            {active && (
              <button
                type="button"
                onClick={() => void act("cancel")}
                className="rounded border px-3 py-1.5 text-sm"
              >
                Cancel
              </button>
            )}
            <button
              type="button"
              onClick={() => {
                setSched(null);
                setError(null);
              }}
              className="rounded border px-3 py-1.5 text-sm"
            >
              New
            </button>
          </div>
        </>
      )}

      <ErrorNote message={error} />
      {toast}
    </Card>
  );
}
