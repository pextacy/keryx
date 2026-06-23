"use client";

import { useState } from "react";
import { errorMessage, postJson } from "@/lib/api";
import type { QfResponse } from "@/lib/capabilities";
import { Card, ErrorNote, Field } from "./Card";

interface ProjectRow {
  wallet: string;
  contributions: string; // comma-separated amounts
}

const SEED: ProjectRow[] = [
  { wallet: "0x" + "a".repeat(40), contributions: "1,1,1,1" },
  { wallet: "0x" + "b".repeat(40), contributions: "4" },
];

export function QfPanel() {
  const [pool, setPool] = useState("0.01");
  const [projects, setProjects] = useState<ProjectRow[]>(SEED);
  const [res, setRes] = useState<QfResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function setProject(i: number, patch: Partial<ProjectRow>) {
    setProjects((prev) => prev.map((p, j) => (j === i ? { ...p, ...patch } : p)));
  }

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const body = {
        pool,
        projects: projects.map((p) => ({
          wallet: p.wallet,
          contributions: p.contributions
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean),
        })),
      };
      setRes(await postJson<QfResponse>("/api/qf", body));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="Quadratic funding" subtitle="Breadth beats size: many small backers win (PA 03/07)">
      <Field label="Match pool (USDC)">
        <input
          value={pool}
          onChange={(e) => setPool(e.target.value)}
          className="w-32 rounded border border-outline-variant/40 bg-surface-container-lowest text-on-surface placeholder:text-outline px-2 py-1 font-mono"
        />
      </Field>

      <div className="mt-3 space-y-2">
        {projects.map((p, i) => (
          <div key={i} className="flex gap-2">
            <input
              value={p.wallet}
              onChange={(e) => setProject(i, { wallet: e.target.value })}
              className="flex-1 rounded border border-outline-variant/40 bg-surface-container-lowest text-on-surface placeholder:text-outline px-2 py-1 font-mono text-xs"
              placeholder="0x project"
            />
            <input
              value={p.contributions}
              onChange={(e) => setProject(i, { contributions: e.target.value })}
              className="w-32 rounded border border-outline-variant/40 bg-surface-container-lowest text-on-surface placeholder:text-outline px-2 py-1 font-mono text-xs"
              placeholder="1,1,1"
            />
          </div>
        ))}
        <button
          type="button"
          onClick={() => setProjects((prev) => [...prev, { wallet: "", contributions: "1" }])}
          className="text-sm text-primary-fixed-dim"
        >
          + project
        </button>
      </div>

      <button
        type="button"
        onClick={submit}
        disabled={busy}
        className="mt-4 rounded bg-primary-fixed-dim px-4 py-2 text-on-primary-fixed font-bold disabled:opacity-50"
      >
        {busy ? "Matching…" : "Match pool"}
      </button>

      <ErrorNote message={error} />

      {res && (
        <ul className="mt-4 space-y-1 text-sm">
          {res.projects.map((p) => (
            <li key={p.wallet} className="flex items-center justify-between font-mono">
              <span className="truncate">
                {p.wallet.slice(0, 12)}… · {p.backers} backers · raised {p.direct_total}
              </span>
              <span className="text-secondary-fixed-dim">+{p.match}</span>
            </li>
          ))}
          <li className="mt-1 border-t pt-1 text-xs text-on-surface-variant">
            total matched {res.total_matched} USDC
          </li>
        </ul>
      )}
    </Card>
  );
}
