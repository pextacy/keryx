import { StatusHeader } from "./_panels/StatusHeader";
import { CheatsheetPanel } from "./_panels/CheatsheetPanel";
import { CapabilityIndexPanel } from "./_panels/CapabilityIndexPanel";
import { AgentToolsPanel } from "./_panels/AgentToolsPanel";
import { TractionPanel } from "./_panels/TractionPanel";
import { MetricsPanel } from "./_panels/MetricsPanel";
import { SendPanel } from "./_panels/SendPanel";
import { PayoutPanel } from "./_panels/PayoutPanel";
import { BondPanel } from "./_panels/BondPanel";
import { StreamPanel } from "./_panels/StreamPanel";
import { RoyaltiesPanel } from "./_panels/RoyaltiesPanel";
import { QfPanel } from "./_panels/QfPanel";
import { RetroPanel } from "./_panels/RetroPanel";
import { OnchainPanel } from "./_panels/OnchainPanel";
import { JobEscrowPanel } from "./_panels/JobEscrowPanel";
import { EscrowPanel } from "./_panels/EscrowPanel";
import { SwapPanel } from "./_panels/SwapPanel";
import { MemoFeedPanel } from "./_panels/MemoFeedPanel";
import { WorkflowPanel } from "./_panels/WorkflowPanel";
import { RequestPanel } from "./_panels/RequestPanel";
import { CreditsPanel } from "./_panels/CreditsPanel";
import { TreasuryPanel } from "./_panels/TreasuryPanel";
import { GatewayPanel } from "./_panels/GatewayPanel";

export default function CapabilitiesPage() {
  return (
    <main className="mx-auto max-w-5xl p-8">
      <h1 className="text-3xl font-semibold">Keryx capabilities</h1>
      <p className="mt-1 text-gray-500">
        Nanopayment primitives on Arc — splits, bonds, streaming, royalties, and matching.
        Each settles in test USDC through the agent.
      </p>

      <StatusHeader />

      <div className="mt-6">
        <CheatsheetPanel />
      </div>

      <div className="mt-6 grid gap-6 md:grid-cols-2">
        <CapabilityIndexPanel />
        <AgentToolsPanel />
      </div>

      <div className="mt-6 grid gap-6 md:grid-cols-2">
        <TractionPanel />
        <MetricsPanel />
      </div>

      <div className="mt-6 grid gap-6 md:grid-cols-2">
        <SendPanel />
        <SwapPanel />
        <RequestPanel />
        <CreditsPanel />
        <TreasuryPanel />
        <GatewayPanel />
        <PayoutPanel />
        <BondPanel />
        <EscrowPanel />
        <StreamPanel />
        <RoyaltiesPanel />
        <QfPanel />
        <RetroPanel />
        <OnchainPanel />
        <JobEscrowPanel />
        <WorkflowPanel />
        <MemoFeedPanel />
      </div>
    </main>
  );
}
