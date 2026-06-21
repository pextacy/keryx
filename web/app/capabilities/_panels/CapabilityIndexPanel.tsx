"use client";

import { useEffect, useState } from "react";
import { errorMessage, getJson } from "@/lib/api";
import type { CapabilityIndex, CapabilityEntry } from "@/lib/capabilities";
import { Card, ErrorNote } from "./Card";

const CATEGORY_LABEL: Record<string, string> = {
  split: "Splits & funding",
  settlement: "Settlement primitives",
  provenance: "Provenance",
  credit: "Credits",
  treasury: "Treasury & balances",
  onchain: "On-chain reads",
};

// Reads GET /capabilities and renders the catalog grouped by category, badging each ported
// capability with its Circle upstream — the "what does this do and where's it from" map.
export function CapabilityIndexPanel() {
  const [ix, setIx] = useState<CapabilityIndex | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getJson<CapabilityIndex>("/api/capabilities")
      .then(setIx)
      .catch((err) => setError(errorMessage(err)));
  }, []);

  const groups = ix
    ? Object.entries(
        ix.capabilities.reduce<Record<string, CapabilityEntry[]>>((acc, c) => {
          (acc[c.category] ??= []).push(c);
          return acc;
        }, {}),
      )
    : [];

  return (
    <Card
      title="Capability index"
      subtitle={
        ix
          ? `${ix.count} capabilities · ${ix.ported} ported from Circle open-source repos`
          : "Every primitive and where it came from"
      }
    >
      <ErrorNote message={error} />
      <div className="space-y-4">
        {groups.map(([category, caps]) => (
          <div key={category}>
            <h4 className="text-xs font-semibold uppercase tracking-wide text-gray-400">
              {CATEGORY_LABEL[category] ?? category}
            </h4>
            <ul className="mt-1 space-y-1.5">
              {caps.map((c) => (
                <li key={c.name} className="text-sm">
                  <div className="flex flex-wrap items-baseline gap-x-2">
                    <span className="font-medium">{c.name}</span>
                    {c.upstream && (
                      <span className="rounded bg-blue-50 px-1.5 py-0.5 text-[11px] text-blue-700">
                        {c.upstream}
                      </span>
                    )}
                    <span className="font-mono text-[11px] text-gray-400">
                      {c.endpoints.join("  ")}
                    </span>
                  </div>
                  <div className="text-xs text-gray-500">{c.summary}</div>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </Card>
  );
}
