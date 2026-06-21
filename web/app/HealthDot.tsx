"use client";

import { useEffect, useState } from "react";

type Activity = { settlements: number; volume_usdc: string };

export function HealthDot() {
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

  const color = up === null ? "bg-gray-300" : up ? "bg-green-500" : "bg-red-500";
  const title = up === null ? "checking agent…" : up ? "agent up" : "agent unreachable";
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={`inline-block h-2 w-2 rounded-full ${color}`} title={title} />
      {up && activity && (
        <span className="text-xs text-gray-400" title={`${activity.volume_usdc} USDC settled`}>
          {activity.settlements} settled
        </span>
      )}
    </span>
  );
}
