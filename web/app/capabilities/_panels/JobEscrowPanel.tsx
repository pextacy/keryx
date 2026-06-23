"use client";

import { useState } from "react";
import { errorMessage, getJson } from "@/lib/api";
import type { JobResponse } from "@/lib/capabilities";
import {
  JOB_LIFECYCLE,
  formatExpiry,
  formatUsdc,
  isTerminalFailure,
  lifecycleStep,
  statusColor,
} from "@/lib/escrow";
import { Card, ErrorNote, Field } from "./Card";

// A linear OPEN -> FUNDED -> SUBMITTED -> COMPLETED stepper; off-path REJECTED/EXPIRED
// render as a single terminal pill (arc-escrow lifecycle ported onto ERC-8183).
function LifecycleStepper({ status }: { status: string }) {
  if (isTerminalFailure(status)) {
    return (
      <span className={`rounded px-2 py-0.5 text-xs font-medium ${statusColor(status)}`}>
        {status}
      </span>
    );
  }
  const at = lifecycleStep(status);
  return (
    <ol className="flex items-center gap-1 text-[11px]">
      {JOB_LIFECYCLE.map((step, i) => {
        const done = at >= 0 && i <= at;
        const current = i === at;
        return (
          <li key={step} className="flex items-center gap-1">
            <span
              className={
                "rounded px-1.5 py-0.5 font-medium " +
                (current
                  ? statusColor(step)
                  : done
                    ? "bg-secondary-fixed-dim/10 text-secondary-fixed-dim"
                    : "bg-white/5 text-outline")
              }
            >
              {step}
            </span>
            {i < JOB_LIFECYCLE.length - 1 && (
              <span className={done ? "text-secondary-fixed-dim" : "text-outline-variant"}>→</span>
            )}
          </li>
        );
      })}
    </ol>
  );
}

function Party({ label, addr }: { label: string; addr?: string }) {
  return (
    <div className="flex justify-between gap-2">
      <span className="text-on-surface-variant">{label}</span>
      <span className="truncate font-mono text-xs" title={addr}>
        {addr ? `${addr.slice(0, 10)}…${addr.slice(-4)}` : "—"}
      </span>
    </div>
  );
}

export function JobEscrowPanel() {
  const [jobId, setJobId] = useState("1");
  const [job, setJob] = useState<JobResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    setBusy(true);
    setError(null);
    try {
      setJob(await getJson<JobResponse>(`/api/job/${encodeURIComponent(jobId)}`));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card
      title="Job escrow (ERC-8183)"
      subtitle="A research job with USDC held in escrow — released to the agent on delivery"
    >
      <Field label="Job id">
        <div className="flex gap-2">
          <input
            value={jobId}
            onChange={(e) => setJobId(e.target.value)}
            className="w-24 rounded border border-outline-variant/40 bg-surface-container-lowest text-on-surface placeholder:text-outline px-2 py-1 font-mono"
          />
          <button
            type="button"
            onClick={() => void load()}
            disabled={busy}
            className="rounded border px-3 py-1.5 text-sm disabled:opacity-50"
          >
            {busy ? "Reading…" : "Read escrow"}
          </button>
        </div>
      </Field>

      {job && !job.enabled && (
        <p className="mt-3 text-xs text-error">
          opt-in (disabled) — set the agent&apos;s KERYX_ERC8183_ENABLED to read on-chain jobs
        </p>
      )}
      {job && job.enabled && job.error && (
        <p className="mt-3 text-xs text-error">RPC error: {job.error}</p>
      )}
      {job && job.enabled && job.found === false && (
        <p className="mt-3 text-xs text-on-surface-variant">no job #{job.job_id} on-chain</p>
      )}

      {job && job.enabled && job.found && job.status && (
        <div className="mt-4 space-y-3">
          <LifecycleStepper status={job.status} />
          <dl className="space-y-1 text-sm">
            <div className="flex justify-between">
              <span className="text-on-surface-variant">escrow</span>
              <span className="font-medium text-secondary-fixed-dim">{formatUsdc(job.budget_usdc)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-on-surface-variant">expires</span>
              <span className="font-mono text-xs">{formatExpiry(job.expired_at)}</span>
            </div>
            <Party label="client" addr={job.client} />
            <Party label="provider (agent)" addr={job.provider} />
            <Party label="evaluator" addr={job.evaluator} />
          </dl>
          {job.description && (
            <p className="rounded bg-white/5 px-2 py-1 text-xs text-on-surface-variant">{job.description}</p>
          )}
        </div>
      )}

      <ErrorNote message={error} />
    </Card>
  );
}
