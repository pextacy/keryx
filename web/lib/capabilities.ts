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

export interface RetroProjectResult {
  wallet: string;
  impact: number;
  award: string;
  settled: boolean;
  tx_hash: string | null;
}

export interface RetroResponse {
  pool: string;
  projects: RetroProjectResult[];
  total_awarded: string;
}

export interface SendResponse {
  to: string;
  amount: string;
  memo: string;
  settled: boolean;
  tx_hash: string | null;
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

export interface SwapResponse {
  token_in?: string;
  token_out?: string;
  amount_in?: string;
  amount_out?: string;
  app_fee_bps?: number;
  app_fee?: string;
  effective_rate?: string;
  to?: string;
  settled?: boolean;
  tx_hash?: string | null;
  error?: string;
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
  expired_at?: number;
  status?: string;
  hook?: string;
  error?: string;
}

export interface ValidationResponse {
  enabled: boolean;
  found?: boolean;
  validator?: string;
  agent_id?: number;
  response?: number;
  passed?: boolean;
  tag?: string;
  error?: string;
}

export interface ReputationResponse {
  enabled: boolean;
  recorded: boolean;
  agent_id?: number;
  tx_hash?: string;
  reason?: string;
}

export interface CircleTxResponse {
  enabled: boolean;
  tx_id?: string;
  transaction?: Record<string, unknown>;
  error?: string;
}

export interface ReconcileResponse {
  enabled: boolean;
  ledger_rows: number;
  verified?: number;
  unverified?: number;
  reconciled_usdc?: string;
  in_sync?: boolean;
}

export interface CitationMetrics {
  total_settled_usdc: string;
  citations_settled: number;
  distinct_author_wallets: number;
  distinct_sessions: number;
  external_share_pct: number;
}

export interface StatusResponse {
  rail: string;
  grounding_threshold: number;
  sources_indexed: number;
  llm_enabled: boolean;
  embedder: string;
  capabilities: {
    erc8004: boolean;
    erc8183: boolean;
    circle_wallets: boolean;
    chain_verified_ledger: boolean;
  };
  traction: TractionResponse;
  citation_metrics: CitationMetrics;
}
