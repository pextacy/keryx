"use client";

import { useEffect, useState } from "react";
import { getJson } from "@/lib/api";
import type { StatusResponse } from "@/lib/capabilities";

function Badge({ label, on }: { label: string; on: boolean }) {
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-xs ${on ? "bg-green-100 text-green-800" : "bg-gray-100 text-gray-500"}`}
    >
      {label}
    </span>
  );
}

export function StatusHeader() {
  const [s, setS] = useState<StatusResponse | null>(null);
  const [down, setDown] = useState(false);

  useEffect(() => {
    getJson<StatusResponse>("/api/status")
      .then(setS)
      .catch(() => setDown(true));
  }, []);

  if (down) {
    return (
      <p className="mt-4 rounded bg-amber-50 p-2 text-sm text-amber-800">
        Agent unreachable — start it with <code>make agent</code> (or set <code>AGENT_URL</code>).
      </p>
    );
  }
  if (!s) return null;

  return (
    <div className="mt-4 flex flex-wrap items-center gap-2 rounded-lg border border-gray-200 p-3 text-sm">
      <span className="font-mono text-green-700">{s.traction.total_volume_usdc} USDC</span>
      <span className="text-gray-500">settled · {s.traction.total_payments} payments</span>
      <span className="mx-1 text-gray-300">|</span>
      <Badge label={`rail: ${s.rail}`} on={s.rail !== "MockRail"} />
      <Badge label={s.embedder === "VoyageEmbedder" ? "dense embeddings" : "lexical"} on={s.embedder === "VoyageEmbedder"} />
      <Badge label="Claude judge" on={s.llm_enabled} />
      <Badge label="ERC-8004" on={s.capabilities.erc8004} />
      <Badge label="ERC-8183" on={s.capabilities.erc8183} />
      <Badge label="Circle Wallets" on={s.capabilities.circle_wallets} />
      <Badge label="chain ledger" on={s.capabilities.chain_verified_ledger} />
    </div>
  );
}
