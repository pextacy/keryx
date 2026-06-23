// Shapes returned by the agent's POST /ask — kept in sync with agent/main.py.

export interface Citation {
  source_url: string;
  g: number;
  amount: string;
  tx_hash: string | null;
  cited: boolean;
  author_wallet?: string | null;
}

export interface Attestation {
  query_hash: string;
  answer_hash: string;
  agent_pubkey: string;
  ts: number;
  signature: string | null;
  verified: boolean;
}

export interface AskResponse {
  answer: string;
  total_settled: string;
  citations: Citation[];
  counts: { cited: number; evaluated_not_cited: number };
  attestation: Attestation;
}

// Arc block explorer (arcscan, Blockscout-style). Resolved from the selected
// network via NEXT_PUBLIC_ARC_EXPLORER (default Arc Testnet), so the same build
// points at testnet or mainnet by env. Matches Circle's BLOCK_EXPLORERS map.
export const ARC_NETWORK = process.env.NEXT_PUBLIC_KERYX_NETWORK ?? "testnet";
export const ARC_EXPLORER =
  process.env.NEXT_PUBLIC_ARC_EXPLORER ?? "https://testnet.arcscan.app";
export const ARC_EXPLORER_TX = `${ARC_EXPLORER}/tx/`;

// Source URLs come from the agent (ultimately from external sources), so only render
// them as links when they use a safe scheme — never `javascript:` etc. Falls back to "#".
export function safeHref(url: string | null | undefined): string {
  if (!url) return "#";
  try {
    const u = new URL(url, "http://localhost");
    return u.protocol === "http:" || u.protocol === "https:" ? url : "#";
  } catch {
    return "#";
  }
}
