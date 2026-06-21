"use client";

import { useState } from "react";
import { errorMessage, getJson, postJson } from "@/lib/api";
import type {
  ApproveResponse,
  WorkflowExecuteResponse,
  WorkflowResponse,
} from "@/lib/capabilities";
import { useToast } from "@/app/Toast";
import { Card, ErrorNote, Field } from "./Card";
import { TxLink } from "./TxLink";

type Row = { to: string; amount: string };

// Surfaces the circle-ooak intent -> approve -> execute guard: draft a batch of settlements,
// approve it once (-> wfid), then execute each in order. The agent rejects any execute that
// doesn't match the approved next action, so nothing settles that wasn't approved.
export function WorkflowPanel() {
  const { toast, notify } = useToast();
  const [rows, setRows] = useState<Row[]>([
    { to: "0x" + "a".repeat(40), amount: "0.01" },
    { to: "0x" + "b".repeat(40), amount: "0.02" },
  ]);
  const [wfid, setWfid] = useState<string | null>(null);
  const [wf, setWf] = useState<WorkflowResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const locked = wfid !== null;

  function update(i: number, patch: Partial<Row>) {
    setRows((rs) => rs.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  }
  function addRow() {
    setRows((rs) => [...rs, { to: "0x" + "c".repeat(40), amount: "0.01" }]);
  }
  function removeRow(i: number) {
    setRows((rs) => (rs.length > 1 ? rs.filter((_, j) => j !== i) : rs));
  }

  async function refresh(id: string) {
    setWf(await getJson<WorkflowResponse>(`/api/workflow/${id}`));
  }

  async function approve() {
    setBusy(true);
    setError(null);
    try {
      const intents = rows.map((r) => ({ to: r.to, amount: r.amount, kind: "workflow" }));
      const r = await postJson<ApproveResponse>("/api/workflow/approve", { intents });
      if (r.error || !r.wfid) {
        setError(r.error ?? "approve failed");
        return;
      }
      setWfid(r.wfid);
      await refresh(r.wfid);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function executeNext() {
    if (!wfid || !wf || wf.cursor === undefined) return;
    const next = rows[wf.cursor];
    if (!next) return;
    setBusy(true);
    setError(null);
    try {
      const r = await postJson<WorkflowExecuteResponse>(`/api/workflow/${wfid}/execute`, {
        to: next.to,
        amount: next.amount,
        kind: "workflow",
      });
      if (r.error) setError(r.error);
      else if (r.settled) notify(`Settled ${r.amount} USDC`, r.tx_hash);
      await refresh(wfid);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  function reset() {
    setWfid(null);
    setWf(null);
    setError(null);
  }

  const done = wf?.status === "completed";

  return (
    <Card
      title="Approved settlements (circle-ooak)"
      subtitle="Approve a batch once, then execute in order — nothing settles that wasn't approved"
    >
      <div className="space-y-2">
        {rows.map((r, i) => {
          const isNext = locked && wf?.cursor === i && !done;
          return (
            <div
              key={i}
              className={`flex items-center gap-2 rounded p-1 ${isNext ? "bg-amber-50" : ""}`}
            >
              <span className="w-4 text-xs text-gray-400">{i + 1}</span>
              <input
                value={r.to}
                onChange={(e) => update(i, { to: e.target.value })}
                disabled={locked}
                className="flex-1 rounded border border-gray-300 px-2 py-1 font-mono text-xs disabled:bg-gray-50"
              />
              <input
                value={r.amount}
                onChange={(e) => update(i, { amount: e.target.value })}
                disabled={locked}
                className="w-20 rounded border border-gray-300 px-2 py-1 font-mono text-xs disabled:bg-gray-50"
              />
              {!locked && rows.length > 1 && (
                <button
                  type="button"
                  onClick={() => removeRow(i)}
                  className="text-xs text-gray-400 hover:text-red-600"
                >
                  ✕
                </button>
              )}
            </div>
          );
        })}
      </div>

      {!locked && (
        <div className="mt-3 flex gap-2">
          <button type="button" onClick={addRow} className="rounded border px-3 py-1.5 text-sm">
            + Add
          </button>
          <button
            type="button"
            onClick={() => void approve()}
            disabled={busy}
            className="rounded bg-black px-3 py-1.5 text-sm text-white disabled:opacity-50"
          >
            {busy ? "…" : `Approve ${rows.length}`}
          </button>
        </div>
      )}

      {locked && wf && (
        <div className="mt-4">
          <Field label={`Workflow ${wf.wfid}`}>
            <div className="flex items-center gap-3 text-sm">
              <span
                className={`rounded px-2 py-0.5 text-xs font-medium ${
                  done ? "bg-green-100 text-green-700" : "bg-amber-100 text-amber-700"
                }`}
              >
                {wf.status}
              </span>
              <span className="text-gray-500">{wf.remaining} remaining</span>
            </div>
          </Field>

          <ol className="mt-2 space-y-1 text-xs">
            {wf.actions?.map((a, i) => (
              <li key={i} className="flex items-center gap-2 font-mono">
                <span className={a.status === "completed" ? "text-green-600" : "text-gray-400"}>
                  {a.status === "completed" ? "✓" : "○"}
                </span>
                <span className="text-gray-500">#{i + 1}</span>
                {a.result ? (
                  <TxLink hash={a.result} prefix="tx" />
                ) : (
                  <span className="text-gray-400">{a.status}</span>
                )}
              </li>
            ))}
          </ol>

          <div className="mt-3 flex gap-2">
            <button
              type="button"
              onClick={() => void executeNext()}
              disabled={busy || done}
              className="rounded bg-black px-3 py-1.5 text-sm text-white disabled:opacity-50"
            >
              {done ? "Done" : busy ? "…" : "Execute next"}
            </button>
            <button type="button" onClick={reset} className="rounded border px-3 py-1.5 text-sm">
              New batch
            </button>
          </div>
        </div>
      )}

      <ErrorNote message={error} />
      {toast}
    </Card>
  );
}
