import { StatusHeader } from "./_panels/StatusHeader";
import { TractionPanel } from "./_panels/TractionPanel";
import { MetricsPanel } from "./_panels/MetricsPanel";
import { PayoutPanel } from "./_panels/PayoutPanel";
import { BondPanel } from "./_panels/BondPanel";
import { StreamPanel } from "./_panels/StreamPanel";
import { RoyaltiesPanel } from "./_panels/RoyaltiesPanel";
import { QfPanel } from "./_panels/QfPanel";
import { RetroPanel } from "./_panels/RetroPanel";
import { OnchainPanel } from "./_panels/OnchainPanel";

export default function CapabilitiesPage() {
  return (
    <main className="mx-auto max-w-5xl p-8">
      <h1 className="text-3xl font-semibold">Keryx capabilities</h1>
      <p className="mt-1 text-gray-500">
        Nanopayment primitives on Arc — splits, bonds, streaming, royalties, and matching.
        Each settles in test USDC through the agent.
      </p>

      <StatusHeader />

      <div className="mt-8 grid gap-6 md:grid-cols-2">
        <TractionPanel />
        <MetricsPanel />
      </div>

      <div className="mt-6 grid gap-6 md:grid-cols-2">
        <PayoutPanel />
        <BondPanel />
        <StreamPanel />
        <RoyaltiesPanel />
        <QfPanel />
        <RetroPanel />
        <OnchainPanel />
      </div>
    </main>
  );
}
