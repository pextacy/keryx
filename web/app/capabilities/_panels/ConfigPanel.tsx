"use client";

import { useEffect, useState } from "react";
import { errorMessage, getJson } from "@/lib/api";
import type { ConfigResponse } from "@/lib/capabilities";
import { Card, ErrorNote } from "./Card";

// Live settlement economics + which paths are active — the config knobs (KERYX_*) reviewers
// care about, read straight from GET /config so nothing here is hardcoded in the UI.
export function ConfigPanel() {
  const [cfg, setCfg] = useState<ConfigResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getJson<ConfigResponse>("/api/config")
      .then(setCfg)
      .catch((err) => setError(errorMessage(err)));
  }, []);

  const e = cfg?.economics;
  const rows: { label: string; value: string }[] = e
    ? [
        { label: "USDC floor", value: `${e.usdc_floor}` },
        { label: "Citation toll", value: `${e.citation_toll_min} – ${e.citation_toll_max}` },
        { label: "Grounding threshold T", value: `${e.grounding_threshold}` },
        { label: "Swap app fee", value: `${e.swap_app_fee_bps} bps` },
        { label: "Treasury sweep threshold", value: `${e.treasury_sweep_threshold} USDC` },
      ]
    : [];

  return (
    <Card title="Live economics" subtitle="Settlement knobs read from the agent's config (not hardcoded)">
      <ErrorNote message={error} />
      {cfg && (
        <>
          <dl className="space-y-1 text-sm">
            {rows.map((r) => (
              <div key={r.label} className="flex justify-between">
                <span className="text-on-surface-variant">{r.label}</span>
                <span className="font-mono text-on-surface">{r.value}</span>
              </div>
            ))}
          </dl>
          <div className="mt-3 border-t pt-2 text-xs text-on-surface-variant">
            rail <span className="font-mono text-on-surface">{cfg.rail}</span> · judge{" "}
            <span className="font-mono text-on-surface">{cfg.judge}</span> · {cfg.sources_indexed}{" "}
            sources indexed
          </div>
        </>
      )}
    </Card>
  );
}
