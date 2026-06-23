"use client";

import { useEffect, useState } from "react";
import { errorMessage, getJson } from "@/lib/api";
import type { AgentToolManifest } from "@/lib/capabilities";
import { Card, ErrorNote } from "./Card";

// Reads GET /agent/tools and renders Keryx's primitives as agent tools (the tool-use shape an
// LLM agent consumes). Shows each tool's route, description, and required inputs — proof Keryx
// is agent-callable, not just a UI (circlefin/agent-stack-starter-kits idea).
export function AgentToolsPanel() {
  const [m, setM] = useState<AgentToolManifest | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getJson<AgentToolManifest>("/api/agent/tools")
      .then(setM)
      .catch((err) => setError(errorMessage(err)));
  }, []);

  return (
    <Card
      title="Agent tools"
      subtitle={
        m
          ? `${m.count} primitives exposed as tool-use schemas for an LLM agent`
          : "Keryx's primitives as callable agent tools"
      }
    >
      <ErrorNote message={error} />
      <ul className="space-y-2">
        {m?.tools.map((t) => (
          <li key={t.name} className="text-sm">
            <div className="flex flex-wrap items-baseline gap-x-2">
              <code className="rounded bg-surface-container-high px-1.5 py-0.5 text-[11px] text-white">
                {t.name}
              </code>
              <span className="font-mono text-[11px] text-outline">
                {t.route.method} {t.route.path}
              </span>
            </div>
            <div className="mt-0.5 text-xs text-on-surface-variant">{t.description}</div>
            {t.input_schema.required.length > 0 && (
              <div className="mt-0.5 font-mono text-[11px] text-outline">
                required: {t.input_schema.required.join(", ")}
              </div>
            )}
          </li>
        ))}
      </ul>
    </Card>
  );
}
