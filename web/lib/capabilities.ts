// Response shapes for the agent's capability endpoints — kept in sync with agent/main.py.

export interface PayoutRecipient {
  wallet: string;
  share: string;
  amount: string;
  settled: boolean;
  tx_hash: string | null;
}

export interface PayoutResponse {
  amount: string;
  recipients: PayoutRecipient[];
  total_settled: string;
}

export type BondStatus = "posted" | "released" | "slashed";

export interface BondResponse {
  bond_id: string;
  provider: string;
  claimant: string;
  amount: string;
  status: BondStatus;
  reputation_delta: number;
  tx_hash?: string | null;
  escrow?: { tx_hash?: string; status?: string; error?: string };
  found?: boolean;
  error?: string;
}

export type StreamStatus = "open" | "paused" | "closed";

export interface StreamResponse {
  stream_id: string;
  payer: string;
  payee: string;
  rate: string;
  status: StreamStatus;
  total_settled: string;
  billed?: string;
  tx_hash?: string | null;
  found?: boolean;
  error?: string;
}

export interface RoyaltyRecipient {
  wallet: string;
  plays: number;
  amount: string;
  settled: boolean;
  tx_hash: string | null;
}

export interface RoyaltiesResponse {
  budget: string;
  recipients: RoyaltyRecipient[];
  total_settled: string;
  gated_out: number;
}

export interface QfProjectResult {
  wallet: string;
  backers: number;
  direct_total: string;
  match: string;
  settled: boolean;
  tx_hash: string | null;
}

export interface QfResponse {
  pool: string;
  projects: QfProjectResult[];
  total_matched: string;
}

// On-chain read endpoints all share an opt-in `enabled` flag (default false).
export interface IdentityResponse {
  enabled: boolean;
  agent_address?: string;
  registered?: boolean;
  agent_id?: number;
  owner?: string;
  metadata_uri?: string;
  error?: string;
}

export interface TractionResponse {
  total_volume_usdc: string;
  total_payments: number;
  by_kind: Record<string, { count: number; volume_usdc: string }>;
}

export interface JobResponse {
  enabled: boolean;
  found?: boolean;
  job_id?: number;
  client?: string;
  provider?: string;
  evaluator?: string;
  description?: string;
  budget_usdc?: string;
  status?: string;
  error?: string;
}
