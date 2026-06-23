"use client";

import { ARC_EXPLORER_TX } from "@/lib/types";
import { Copy } from "@/app/Copy";

// An Arc explorer link for a tx hash + a copy button. One place so every panel renders
// tx hashes the same way (truncated link, copyable full hash).
export function TxLink({
  hash,
  prefix = "tx",
  chars = 14,
}: {
  hash: string;
  prefix?: string;
  chars?: number;
}) {
  return (
    <span className="inline-flex items-center gap-1">
      <a href={ARC_EXPLORER_TX + hash} target="_blank" className="text-primary-fixed-dim underline">
        {chars > 0 ? `${prefix} ${hash.slice(0, chars)}…`.trim() : prefix || "tx"}
      </a>
      <Copy text={hash} />
    </span>
  );
}
