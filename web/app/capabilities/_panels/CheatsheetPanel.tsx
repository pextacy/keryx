import { Card } from "./Card";

const ROWS: { name: string; endpoint: string; what: string }[] = [
  { name: "Royalty split", endpoint: "POST /payout", what: "pay every credited contributor in proportion" },
  { name: "User royalties", endpoint: "POST /royalties", what: "a budget pays only who you played, gated" },
  { name: "Quadratic funding", endpoint: "POST /qf", what: "match a pool by breadth (√-sum-squared)" },
  { name: "Retroactive funding", endpoint: "POST /retro", what: "award after the fact by realized impact" },
  { name: "Reputation bond", endpoint: "POST /bond", what: "collateral that slashes to the claimant on default" },
  { name: "Streaming", endpoint: "POST /stream", what: "pay-per-second flow, billed live with no dust" },
  { name: "Send with memo", endpoint: "POST /send", what: "a transfer whose memo carries why it was paid (recibo)" },
  { name: "Stablecoin swap", endpoint: "POST /swap", what: "USDC↔EURC at an app-fee rate (arc-stablecoin-fx)" },
  { name: "Split-bill request", endpoint: "POST /request", what: "a payee splits a total across payers, each fulfils (p2p)" },
  { name: "Prepaid credits", endpoint: "POST /credits/topup", what: "top up once, draw down per action (arc-commerce)" },
  { name: "Approved workflow", endpoint: "POST /workflow/approve", what: "approve a settlement batch, execute in order (circle-ooak)" },
  { name: "Refund / dispute", endpoint: "POST /refund/{tx}", what: "refund to the bound address w/ a reason (refund-protocol)" },
  { name: "Unified balance", endpoint: "GET /balance", what: "one view of settled + credits + open requests" },
  { name: "Receipt feed", endpoint: "GET /memos", what: "structured provenance memos, filterable by kind" },
];

export function CheatsheetPanel() {
  return (
    <Card title="Primitive cheatsheet" subtitle="Every nanopayment primitive, settled in test USDC via the rail">
      <ul className="space-y-2 text-sm">
        {ROWS.map((r) => (
          <li key={r.endpoint} className="flex flex-wrap items-baseline gap-x-2">
            <span className="font-medium">{r.name}</span>
            <code className="rounded bg-gray-100 px-1 text-xs text-gray-600">{r.endpoint}</code>
            <span className="text-gray-500">— {r.what}</span>
          </li>
        ))}
      </ul>
    </Card>
  );
}
