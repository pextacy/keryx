"use client";

import { useState } from "react";
import { errorMessage, getJson, postJson } from "@/lib/api";
import { ARC_EXPLORER_TX } from "@/lib/types";
import type {
  IdentityResponse,
  JobResponse,
  ReputationResponse,
  ValidationResponse,
} from "@/lib/capabilities";
import { Copy } from "@/app/Copy";
import { Card, ErrorNote, Field } from "./Card";

export function OnchainPanel() {
  const [identity, setIdentity] = useState<IdentityResponse | null>(null);
  const [jobId, setJobId] = useState("1");
  const [job, setJob] = useState<JobResponse | null>(null);
  const [hash, setHash] = useState("");
  const [validation, setValidation] = useState<ValidationResponse | null>(null);
  const [repAgent, setRepAgent] = useState("1");
  const [repG, setRepG] = useState("0.9");
  const [rep, setRep] = useState<ReputationResponse | null>(null);
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
      <p className="text-xs text-error">opt-in (disabled) — set the agent&apos;s KERYX_*_ENABLED</p>
    );

  return (
    <Card title="On-chain reads" subtitle="ERC-8004 identity/reputation/validation + ERC-8183 job (opt-in)">
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
          {identity.agent_id !== undefined && <div>agent_id: {identity.agent_id}</div>}
          {disabledNote(identity.enabled)}
        </div>
      )}

      <div className="mt-5">
        <Field label="ERC-8183 job by id">
          <div className="flex gap-2">
            <input
              value={jobId}
              onChange={(e) => setJobId(e.target.value)}
              className="w-24 rounded border border-outline-variant/40 bg-surface-container-lowest text-on-surface placeholder:text-outline px-2 py-1 font-mono"
            />
            <button
              type="button"
              onClick={() =>
                void load(() => getJson<JobResponse>(`/api/job/${encodeURIComponent(jobId)}`), setJob)
              }
              className="rounded border px-3 py-1.5 text-sm"
            >
              Get job
            </button>
          </div>
        </Field>
      </div>
      {job && (
        <div className="mt-1 font-mono text-xs">
          {job.enabled && job.found ? (
            <span>
              status {job.status} · {job.budget_usdc} USDC
            </span>
          ) : (
            disabledNote(job.enabled)
          )}
        </div>
      )}

      <div className="mt-5">
        <Field label="ERC-8004 validation by request hash">
          <div className="flex gap-2">
            <input
              value={hash}
              onChange={(e) => setHash(e.target.value)}
              placeholder="0x…"
              className="flex-1 rounded border border-outline-variant/40 bg-surface-container-lowest text-on-surface placeholder:text-outline px-2 py-1 font-mono text-xs"
            />
            <button
              type="button"
              disabled={!hash}
              onClick={() =>
                void load(
                  () => getJson<ValidationResponse>(`/api/validation/${encodeURIComponent(hash)}`),
                  setValidation,
                )
              }
              className="rounded border px-3 py-1.5 text-sm disabled:opacity-40"
            >
              Check
            </button>
          </div>
        </Field>
      </div>
      {validation && (
        <div className="mt-1 font-mono text-xs">
          {validation.enabled && validation.found ? (
            <span className={validation.passed ? "text-secondary-fixed-dim" : "text-error"}>
              {validation.passed ? "passed" : "failed"} ({validation.response}) · {validation.tag}
            </span>
          ) : (
            disabledNote(validation.enabled)
          )}
        </div>
      )}

      <div className="mt-5">
        <Field label="Record ERC-8004 reputation (grounding → score)">
          <div className="flex gap-2">
            <input
              value={repAgent}
              onChange={(e) => setRepAgent(e.target.value)}
              className="w-20 rounded border border-outline-variant/40 bg-surface-container-lowest text-on-surface placeholder:text-outline px-2 py-1 font-mono"
              placeholder="agent_id"
            />
            <input
              value={repG}
              onChange={(e) => setRepG(e.target.value)}
              className="w-20 rounded border border-outline-variant/40 bg-surface-container-lowest text-on-surface placeholder:text-outline px-2 py-1 font-mono"
              placeholder="g (0-1)"
            />
            <button
              type="button"
              onClick={() =>
                void load(
                  () =>
                    postJson<ReputationResponse>("/api/reputation", {
                      agent_id: Number(repAgent),
                      g: Number(repG),
                    }),
                  setRep,
                )
              }
              className="rounded border px-3 py-1.5 text-sm"
            >
              Record
            </button>
          </div>
        </Field>
      </div>
      {rep && (
        <div className="mt-1 font-mono text-xs">
          {rep.recorded && rep.tx_hash ? (
            <span className="inline-flex items-center gap-1">
              <a
                href={ARC_EXPLORER_TX + rep.tx_hash}
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary-fixed-dim underline"
              >
                recorded · tx {rep.tx_hash.slice(0, 14)}…
              </a>
              <Copy text={rep.tx_hash} />
            </span>
          ) : (
            <span className="text-on-surface-variant">{rep.reason ?? "not recorded"}</span>
          )}
        </div>
      )}

      <ErrorNote message={error} />
    </Card>
  );
}
