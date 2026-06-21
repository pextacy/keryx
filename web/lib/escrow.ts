// Escrow lifecycle helpers — status colors + amount formatting + a linear stepper.
//
// Ported from circlefin/arc-escrow (vendor/circle/arc-escrow/lib/utils/escrow.ts):
// its STATUS_COLORS map (PENDING|OPEN|LOCKED|CLOSED) and Intl-based formatAmount.
// Here the lifecycle is the ERC-8183 AgenticCommerce job status the agent returns
// from GET /job/{id}: OPEN -> FUNDED -> SUBMITTED -> COMPLETED, with REJECTED/EXPIRED
// as terminal off-path states.

export type JobStatus =
  | "OPEN"
  | "FUNDED"
  | "SUBMITTED"
  | "COMPLETED"
  | "REJECTED"
  | "EXPIRED";

// The happy-path order a job escrow moves through (provider delivers, evaluator releases).
export const JOB_LIFECYCLE: readonly JobStatus[] = [
  "OPEN",
  "FUNDED",
  "SUBMITTED",
  "COMPLETED",
] as const;

// arc-escrow's color idiom, mapped onto the ERC-8183 statuses.
const STATUS_COLORS: Record<JobStatus, string> = {
  OPEN: "text-yellow-700 bg-yellow-100",
  FUNDED: "text-blue-700 bg-blue-100",
  SUBMITTED: "text-indigo-700 bg-indigo-100",
  COMPLETED: "text-green-700 bg-green-100",
  REJECTED: "text-red-700 bg-red-100",
  EXPIRED: "text-gray-600 bg-gray-100",
};

export function statusColor(status: string): string {
  return STATUS_COLORS[status as JobStatus] ?? "text-gray-600 bg-gray-100";
}

// Index of a status on the happy path, or -1 for off-path/terminal (REJECTED/EXPIRED).
export function lifecycleStep(status: string): number {
  return JOB_LIFECYCLE.indexOf(status as JobStatus);
}

export function isTerminalFailure(status: string): boolean {
  return status === "REJECTED" || status === "EXPIRED";
}

// Ported from arc-escrow formatAmount, kept side-effect free (returns "" on bad input
// instead of throwing — this is display-only and the agent already validated upstream).
export function formatUsdc(amount: string | number | undefined): string {
  if (amount === undefined) return "—";
  const n = typeof amount === "number" ? amount : Number(amount);
  if (!Number.isFinite(n)) return "—";
  try {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 2,
      maximumFractionDigits: 6,
    }).format(n);
  } catch {
    return `${n} USDC`;
  }
}

// "year-2100 anchor" sentinel the agent uses for non-expiring escrow -> show as "none".
export function formatExpiry(expiredAt: number | undefined): string {
  if (!expiredAt) return "none";
  const FAR_FUTURE = 4_102_444_800; // 2100-01-01 UTC
  if (expiredAt >= FAR_FUTURE) return "none (anchor)";
  return new Date(expiredAt * 1000).toISOString().slice(0, 10);
}
