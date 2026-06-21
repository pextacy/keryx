"use client";

import { useCallback, useState } from "react";
import { ARC_EXPLORER_TX } from "@/lib/types";
import { Copy } from "./Copy";

type Toast = { message: string; tx?: string | null };

// A lightweight settlement toast: call notify(message, tx) after a settle; the returned
// node renders a fixed bottom-right card with the tx hash + copy, auto-dismissing after 4s.
// No context/provider needed — each panel owns its own toast via the hook.
export function useToast(): { toast: React.ReactNode; notify: (message: string, tx?: string | null) => void } {
  const [current, setCurrent] = useState<Toast | null>(null);

  const notify = useCallback((message: string, tx?: string | null) => {
    setCurrent({ message, tx });
    setTimeout(() => setCurrent(null), 4000);
  }, []);

  const toast = current ? (
    <div className="fixed bottom-4 right-4 z-50 max-w-xs rounded-lg border border-green-200 bg-white px-4 py-3 shadow-lg">
      <div className="flex items-center gap-2">
        <span className="text-green-600">✓</span>
        <span className="text-sm font-medium text-gray-800">{current.message}</span>
      </div>
      {current.tx && (
        <div className="mt-1 flex items-center gap-1">
          <a
            href={ARC_EXPLORER_TX + current.tx}
            target="_blank"
            className="font-mono text-xs text-blue-600 underline"
          >
            tx {current.tx.slice(0, 16)}…
          </a>
          <Copy text={current.tx} />
        </div>
      )}
    </div>
  ) : null;

  return { toast, notify };
}
