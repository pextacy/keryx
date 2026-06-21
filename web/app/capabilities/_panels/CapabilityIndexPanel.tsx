"use client";

import { useEffect, useState } from "react";
import { errorMessage, getJson } from "@/lib/api";
import type { CapabilityIndex, CapabilityEntry } from "@/lib/capabilities";
import { Copy } from "@/app/Copy";
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
  const [category, setCategory] = useState("");
  const [portedOnly, setPortedOnly] = useState(false);
  const [open, setOpen] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getJson<CapabilityIndex>("/api/capabilities")
      .then(setIx)
      .catch((err) => setError(errorMessage(err)));
  }, []);

  const filtered = (ix?.capabilities ?? []).filter(
    (c) => (!category || c.category === category) && (!portedOnly || c.ported),
  );
  const groups = Object.entries(
    filtered.reduce<Record<string, CapabilityEntry[]>>((acc, c) => {
      (acc[c.category] ??= []).push(c);
      return acc;
    }, {}),
  );

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

      {ix && (
        <div className="mb-3 flex flex-wrap items-center gap-2 text-xs">
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="rounded border border-gray-300 px-2 py-1"
          >
            <option value="">all categories</option>
            {Object.keys(ix.by_category).map((c) => (
              <option key={c} value={c}>
                {CATEGORY_LABEL[c] ?? c} ({ix.by_category[c]})
              </option>
            ))}
          </select>
          <label className="flex items-center gap-1 text-gray-600">
            <input
              type="checkbox"
              checked={portedOnly}
              onChange={(e) => setPortedOnly(e.target.checked)}
            />
            ported only
          </label>
          <span className="text-gray-400">{filtered.length} shown</span>
        </div>
      )}

      <div className="space-y-4">
        {groups.map(([cat, caps]) => (
          <div key={cat}>
            <h4 className="text-xs font-semibold uppercase tracking-wide text-gray-400">
              {CATEGORY_LABEL[cat] ?? cat}
            </h4>
            <ul className="mt-1 space-y-1.5">
              {caps.map((c) => (
                <li key={c.name} className="text-sm">
                  <button
                    type="button"
                    onClick={() => setOpen(open === c.name ? null : c.name)}
                    className="flex w-full flex-wrap items-baseline gap-x-2 text-left"
                  >
                    <span className="text-gray-400">{open === c.name ? "▾" : "▸"}</span>
                    <span className="font-medium">{c.name}</span>
                    {c.upstream && (
                      <span className="rounded bg-blue-50 px-1.5 py-0.5 text-[11px] text-blue-700">
                        {c.upstream}
                      </span>
                    )}
                    <span className="font-mono text-[11px] text-gray-400">
                      {c.endpoints.join("  ")}
                    </span>
                  </button>
                  <div className="ml-4 text-xs text-gray-500">{c.summary}</div>
                  {open === c.name && c.example && (
                    <div className="ml-4 mt-1 flex items-start gap-1 rounded bg-gray-900 p-2">
                      <code className="flex-1 overflow-x-auto whitespace-pre-wrap break-all font-mono text-[11px] text-gray-100">
                        {c.example}
                      </code>
                      <Copy text={c.example} />
                    </div>
                  )}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </Card>
  );
}
