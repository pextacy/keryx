"use client";

import { useEffect, useState } from "react";

export function HealthDot() {
  const [up, setUp] = useState<boolean | null>(null);

  useEffect(() => {
    const ping = async () => {
      try {
        const r = await fetch("/api/healthz", { cache: "no-store" });
        setUp(r.ok);
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
  return <span className={`inline-block h-2 w-2 rounded-full ${color}`} title={title} />;
}
