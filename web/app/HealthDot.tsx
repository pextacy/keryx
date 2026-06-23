"use client";

import { useEffect, useState } from "react";

type Activity = { settlements: number; volume_usdc: string };

function useAgentHealth() {
  const [up, setUp] = useState<boolean | null>(null);
  const [activity, setActivity] = useState<Activity | null>(null);

  useEffect(() => {
    const ping = async () => {
      try {
        const r = await fetch("/api/healthz", { cache: "no-store" });
        setUp(r.ok);
        if (r.ok) {
          const body = (await r.json()) as { activity?: Activity };
          if (body.activity) setActivity(body.activity);
        }
      } catch {
        setUp(false);
      }
    };
    ping();
    const id = setInterval(ping, 10000);
    return () => clearInterval(id);
  }, []);

  return { up, activity };
}

// The nav chip — live network indicator wired to the agent's /api/healthz.
export function NetworkStatus() {
  const { up, activity } = useAgentHealth();
  const live = up === true;
  const label = up === null ? "Connecting…" : live ? "" : "Agent Offline";
  const color = up === null ? "text-on-surface-variant" : live ? "text-secondary-fixed-dim" : "text-error";
  const ring = up === null ? "border-white/15" : live ? "border-secondary-fixed-dim/30" : "border-error/30";
  const dot = up === null ? "bg-on-surface-variant" : live ? "bg-secondary-fixed-dim" : "bg-error";
  return (
    <span
      className={`hidden items-center gap-2 rounded-full border ${ring} bg-white/5 px-3 py-1 font-label-caps text-[10px] ${color} sm:inline-flex`}
      title={activity ? `${activity.volume_usdc} USDC settled · ${activity.settlements} payments` : label}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${dot} ${live ? "animate-pulse" : ""}`} />
      {label}
    </span>
  );
}

// Legacy inline dot (kept for any other callers).
export function HealthDot() {
  const { up, activity } = useAgentHealth();
  const color = up === null ? "bg-on-surface-variant" : up ? "bg-secondary-fixed-dim" : "bg-error";
  const title = up === null ? "checking agent…" : up ? "agent up" : "agent unreachable";
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={`inline-block h-2 w-2 rounded-full ${color}`} title={title} />
      {up && activity && (
        <span className="font-mono-data text-xs text-on-surface-variant">
          {activity.settlements} settled
        </span>
      )}
    </span>
  );
}
