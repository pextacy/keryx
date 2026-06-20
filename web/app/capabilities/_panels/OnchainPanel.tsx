"use client";

import { useState } from "react";
import { errorMessage, getJson } from "@/lib/api";
import type { IdentityResponse, JobResponse } from "@/lib/capabilities";
import { Card, ErrorNote, Field } from "./Card";

export function OnchainPanel() {
  const [identity, setIdentity] = useState<IdentityResponse | null>(null);
  const [jobId, setJobId] = useState("1");
  const [job, setJob] = useState<JobResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load<T>(fn: () => Promise<T>, set: (v: T) => void) {
    setError(null);
    try {
      set(await fn());
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  const disabledNote = (enabled: boolean) =>
    !enabled && (
      <p className="text-xs text-amber-700">
        opt-in (disabled) — set KERYX_ERC8004_ENABLED / KERYX_ERC8183_ENABLED on the agent
      </p>
    );

  return (
    <Card title="On-chain reads" subtitle="ERC-8004 identity + ERC-8183 job state (opt-in)">
      <button
        type="button"
        onClick={() => void load(() => getJson<IdentityResponse>("/api/identity"), setIdentity)}
        className="rounded border px-3 py-1.5 text-sm"
      >
        Load agent identity
      </button>
      {identity && (
        <div className="mt-2 space-y-1 font-mono text-xs">
          <div>agent: {identity.agent_address ?? "—"}</div>
          {identity.enabled && <div>registered: {String(identity.registered ?? false)}</div>}
          {identity.agent_id !== undefined && <div>agent_id: {identity.agent_id}</div>}
          {disabledNote(identity.enabled)}
        </div>
      )}

      <div className="mt-5">
        <Field label="Look up ERC-8183 job by id">
          <div className="flex gap-2">
            <input
              value={jobId}
              onChange={(e) => setJobId(e.target.value)}
              className="w-24 rounded border border-gray-300 px-2 py-1 font-mono"
            />
            <button
              type="button"
              onClick={() =>
                void load(
                  () => getJson<JobResponse>(`/api/job/${encodeURIComponent(jobId)}`),
                  setJob,
                )
              }
              className="rounded border px-3 py-1.5 text-sm"
            >
              Get job
            </button>
          </div>
        </Field>
      </div>
      {job && (
        <div className="mt-2 space-y-1 font-mono text-xs">
          {job.enabled && job.found ? (
            <>
              <div>status: {job.status}</div>
              <div>budget: {job.budget_usdc} USDC</div>
              <div>provider: {job.provider}</div>
            </>
          ) : job.enabled ? (
            <div className="text-gray-500">job {jobId} not found</div>
          ) : null}
          {disabledNote(job.enabled)}
        </div>
      )}

      <ErrorNote message={error} />
    </Card>
  );
}
