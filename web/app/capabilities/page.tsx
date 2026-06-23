import { Section } from "./_panels/Section";
import { AccordionRow } from "./_panels/Accordion";
import { StatusHeader } from "./_panels/StatusHeader";
import { CheatsheetPanel } from "./_panels/CheatsheetPanel";
import { CapabilityIndexPanel } from "./_panels/CapabilityIndexPanel";
import { AgentToolsPanel } from "./_panels/AgentToolsPanel";
import { ConfigPanel } from "./_panels/ConfigPanel";
import { TractionPanel } from "./_panels/TractionPanel";
import { MetricsPanel } from "./_panels/MetricsPanel";
import { HistoryPanel } from "./_panels/HistoryPanel";
import { SendPanel } from "./_panels/SendPanel";
import { PayoutPanel } from "./_panels/PayoutPanel";
import { BondPanel } from "./_panels/BondPanel";
import { StreamPanel } from "./_panels/StreamPanel";
import { SchedulePanel } from "./_panels/SchedulePanel";
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
import { OrderPanel } from "./_panels/OrderPanel";
import { TreasuryPanel } from "./_panels/TreasuryPanel";
import { GatewayPanel } from "./_panels/GatewayPanel";

export default function CapabilitiesPage() {
  return (
    <main className="mx-auto max-w-3xl px-gutter pb-24 pt-24">
      <h1 className="font-display-lg text-display-lg text-on-surface">Nanopayment Primitives</h1>
      <p className="mt-1 max-w-2xl text-on-surface-variant">
        Open a primitive to run it — each settles in test USDC through the agent.
        Grouped by method: POST moves money, GET reads it.
      </p>

      <StatusHeader />

      {/* POST — anything that settles or changes state. Pick one and open it. */}
      <Section
        method="POST"
        title="Actions & settlements"
        subtitle="Move USDC: split, stream, bond, swap, escrow, schedule"
        count={16}
        noun="actions"
        storageKey="actions"
      >
        <AccordionRow tone="POST" storageKey="payout" icon="call_split" name="Royalty split" desc="Pay every contributor in proportion" defaultOpen>
          <PayoutPanel />
        </AccordionRow>
        <AccordionRow tone="POST" storageKey="royalties" icon="music_note" name="User royalties" desc="A budget pays only who you played, gated">
          <RoyaltiesPanel />
        </AccordionRow>
        <AccordionRow tone="POST" storageKey="qf" icon="hub" name="Quadratic funding" desc="Match a pool by breadth of backers">
          <QfPanel />
        </AccordionRow>
        <AccordionRow tone="POST" storageKey="retro" icon="emoji_events" name="Retroactive funding" desc="Award after the fact by realized impact">
          <RetroPanel />
        </AccordionRow>
        <AccordionRow tone="POST" storageKey="bond" icon="verified_user" name="Reputation bond" desc="Collateral that slashes on default">
          <BondPanel />
        </AccordionRow>
        <AccordionRow tone="POST" storageKey="stream" icon="water_drop" name="Streaming" desc="Pay-per-second flow, billed live with no dust">
          <StreamPanel />
        </AccordionRow>
        <AccordionRow tone="POST" storageKey="escrow" icon="lock" name="Milestone escrow" desc="Lock a total, release per milestone">
          <EscrowPanel />
        </AccordionRow>
        <AccordionRow tone="POST" storageKey="schedule" icon="event_repeat" name="Recurring schedule" desc="A fixed amount on a subscription cadence">
          <SchedulePanel />
        </AccordionRow>
        <AccordionRow tone="POST" storageKey="send" icon="send" name="Send with memo" desc="A transfer whose memo carries why it was paid">
          <SendPanel />
        </AccordionRow>
        <AccordionRow tone="POST" storageKey="swap" icon="swap_horiz" name="Stablecoin swap" desc="USDC ↔ EURC at an app-fee rate">
          <SwapPanel />
        </AccordionRow>
        <AccordionRow tone="POST" storageKey="request" icon="receipt_long" name="Split-bill request" desc="Split a total across payers, each fulfils">
          <RequestPanel />
        </AccordionRow>
        <AccordionRow tone="POST" storageKey="credits" icon="account_balance_wallet" name="Prepaid credits" desc="Top up once, draw down per action">
          <CreditsPanel />
        </AccordionRow>
        <AccordionRow tone="POST" storageKey="order" icon="shopping_cart" name="Order checkout" desc="Create an order and settle at checkout">
          <OrderPanel />
        </AccordionRow>
        <AccordionRow tone="POST" storageKey="gateway" icon="lan" name="Gateway balance" desc="Deposit from many chains, spend as one">
          <GatewayPanel />
        </AccordionRow>
        <AccordionRow tone="POST" storageKey="treasury" icon="savings" name="Treasury sweep" desc="Sweep accumulated inflows to a destination">
          <TreasuryPanel />
        </AccordionRow>
        <AccordionRow tone="POST" storageKey="workflow" icon="account_tree" name="Approved workflow" desc="Approve a settlement batch, execute in order">
          <WorkflowPanel />
        </AccordionRow>
      </Section>

      {/* GET — reads and monitoring. Mixed panels sit here when their main job is to observe. */}
      <Section
        method="GET"
        title="Reads & monitoring"
        subtitle="Inspect state: traction, metrics, history, memos, on-chain identity"
        count={9}
        noun="reads"
        storageKey="reads"
      >
        <AccordionRow tone="GET" storageKey="capabilities" icon="grid_view" name="Capability index" desc="Every primitive the agent exposes">
          <CapabilityIndexPanel />
        </AccordionRow>
        <AccordionRow tone="GET" storageKey="tools" icon="construction" name="Agent tools" desc="Tool schemas the agent can call">
          <AgentToolsPanel />
        </AccordionRow>
        <AccordionRow tone="GET" storageKey="config" icon="tune" name="Config" desc="Live rail, embedder, and feature flags">
          <ConfigPanel />
        </AccordionRow>
        <AccordionRow tone="GET" storageKey="traction" icon="trending_up" name="Traction" desc="Settled volume rolled up, plus demo controls">
          <TractionPanel />
        </AccordionRow>
        <AccordionRow tone="GET" storageKey="metrics" icon="monitoring" name="Metrics" desc="Citation and settlement breakdown">
          <MetricsPanel />
        </AccordionRow>
        <AccordionRow tone="GET" storageKey="history" icon="history" name="History" desc="Recent settlements, newest first">
          <HistoryPanel />
        </AccordionRow>
        <AccordionRow tone="GET" storageKey="memos" icon="forum" name="Receipt feed" desc="Provenance memos, filterable by kind">
          <MemoFeedPanel />
        </AccordionRow>
        <AccordionRow tone="GET" storageKey="job" icon="work" name="Job escrow" desc="Look up an on-chain ERC-8183 job">
          <JobEscrowPanel />
        </AccordionRow>
        <AccordionRow tone="GET" storageKey="onchain" icon="fingerprint" name="On-chain identity" desc="ERC-8004 identity, reputation, validation">
          <OnchainPanel />
        </AccordionRow>
      </Section>

      {/* DOCS — reference. Collapsed by default to keep the console tidy. */}
      <Section
        method="DOCS"
        title="Primitive cheatsheet"
        subtitle="Every primitive and its endpoint, in one list"
        count={18}
        noun="primitives"
        storageKey="reference"
        defaultOpen={false}
        layout="single"
      >
        <CheatsheetPanel />
      </Section>
    </main>
  );
}
