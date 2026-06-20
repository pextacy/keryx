import Link from "next/link";
import { TractionPanel } from "./_panels/TractionPanel";
import { PayoutPanel } from "./_panels/PayoutPanel";
import { BondPanel } from "./_panels/BondPanel";
import { StreamPanel } from "./_panels/StreamPanel";
import { RoyaltiesPanel } from "./_panels/RoyaltiesPanel";
import { QfPanel } from "./_panels/QfPanel";
import { OnchainPanel } from "./_panels/OnchainPanel";

export default function CapabilitiesPage() {
  return (
    <main className="mx-auto max-w-5xl p-8">
      <div className="flex items-baseline justify-between">
        <div>
          <h1 className="text-3xl font-semibold">Keryx capabilities</h1>
          <p className="mt-1 text-gray-500">
            Nanopayment primitives on Arc — splits, bonds, streaming, royalties, and matching.
            Each settles in test USDC through the agent.
          </p>
        </div>
        <Link href="/" className="text-sm text-blue-600 underline">
          ← Ask
        </Link>
      </div>

      <div className="mt-8">
        <TractionPanel />
      </div>

      <div className="mt-6 grid gap-6 md:grid-cols-2">
        <PayoutPanel />
        <BondPanel />
        <StreamPanel />
        <RoyaltiesPanel />
        <QfPanel />
        <OnchainPanel />
      </div>
    </main>
  );
}
