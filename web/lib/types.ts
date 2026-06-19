// Shapes returned by the agent's POST /ask — kept in sync with agent/main.py.

export interface Citation {
  source_url: string;
  g: number;
  amount: string;
  tx_hash: string | null;
  cited: boolean;
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

export const ARC_EXPLORER_TX = "https://explorer.testnet.arc.network/tx/";
