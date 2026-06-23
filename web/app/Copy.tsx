"use client";

import { useState } from "react";

export function Copy({ text, label }: { text: string; label?: string }) {
  const [done, setDone] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setDone(true);
      setTimeout(() => setDone(false), 1200);
    } catch {
      // clipboard may be unavailable (insecure context); ignore
    }
  }

  return (
    <button
      type="button"
      onClick={copy}
      title="Copy"
      className="font-mono-data text-xs text-on-surface-variant transition-colors hover:text-primary-fixed-dim"
    >
      {done ? "✓" : (label ?? "⧉")}
    </button>
  );
}
