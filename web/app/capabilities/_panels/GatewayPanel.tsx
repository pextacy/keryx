"use client";

import { useEffect, useState } from "react";
import { errorMessage, getJson, postJson } from "@/lib/api";
import type { GatewayResponse } from "@/lib/capabilities";
import { useToast } from "@/app/Toast";
import { Card, ErrorNote, Field } from "./Card";
import { TxLink } from "./TxLink";

// Fallback if the agent is offline; the live list comes from GET /gateway/chains.
const FALLBACK_CHAINS = ["arcTestnet", "avalancheFuji", "baseSepolia"];

// Gateway unified balance (ported from arc-multichain-wallet): deposit USDC from several
// source chains into one Arc-spendable balance, with per-chain provenance.
export function GatewayPanel() {
  const { toast, notify } = useToast();
  const [wallet, setWallet] = useState("0x" + "a".repeat(40));
  const [chains, setChains] = useState<string[]>(FALLBACK_CHAINS);
  const [chain, setChain] = useState("avalancheFuji");

  // Reflect the agent's actual supported source chains, so the selector never drifts.
  useEffect(() => {
    getJson<{ chains: string[] }>("/api/gateway/chains")
      .then((d) => {
        if (Array.isArray(d.chains) && d.chains.length) setChains(d.chains);
      })
      .catch(() => setChains(FALLBACK_CHAINS));
  }, []);
  const [amount, setAmount] = useState("0.5");
  const [spendTo, setSpendTo] = useState("0x" + "c".repeat(40));
  const [spendAmt, setSpendAmt] = useState("0.2");
  const [acct, setAcct] = useState<GatewayResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function deposit() {
    setBusy(true);
    setError(null);
    try {
      const r = await postJson<GatewayResponse>("/api/gateway/deposit", { wallet, chain, amount });
      if (r.error) setError(r.error);
      else {
        setAcct(r);
        if (r.deposited) notify(`Deposited ${amount} from ${chain}`, r.tx_hash);
      }
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function spend() {
    setBusy(true);
    setError(null);
    try {
      const r = await postJson<GatewayResponse>("/api/gateway/spend", {
        wallet,
        to: spendTo,
        amount: spendAmt,
      });
      if (r.error) setError(r.error);
      else {
        setAcct(r);
        if (r.spent) notify(`Spent ${r.amount} from unified balance`, r.tx_hash);
      }
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function refresh() {
    setError(null);
    try {
      setAcct(await getJson<GatewayResponse>(`/api/gateway/${encodeURIComponent(wallet)}`));
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <Card
      title="Gateway unified balance"
      subtitle="Deposit USDC from many chains into one Arc-spendable balance (multichain-wallet)"
    >
      <Field label="Wallet">
        <input
          value={wallet}
          onChange={(e) => setWallet(e.target.value)}
          className="w-full rounded border border-outline-variant/40 bg-surface-container-lowest text-on-surface placeholder:text-outline px-2 py-1 font-mono text-xs"
        />
      </Field>

      <div className="mt-3 flex items-end gap-2">
        <Field label="Source chain">
          <select
            value={chain}
            onChange={(e) => setChain(e.target.value)}
            className="rounded border border-outline-variant/40 bg-surface-container-lowest text-on-surface placeholder:text-outline px-2 py-1 text-sm"
          >
            {chains.map((ch) => (
              <option key={ch} className="bg-surface-container">{ch}</option>
            ))}
          </select>
        </Field>
        <Field label="Amount">
          <input
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            className="w-24 rounded border border-outline-variant/40 bg-surface-container-lowest text-on-surface placeholder:text-outline px-2 py-1 font-mono"
          />
        </Field>
        <button
          type="button"
          onClick={() => void deposit()}
          disabled={busy}
          className="mb-1 rounded bg-primary-fixed-dim px-3 py-1.5 text-sm text-on-primary-fixed font-bold disabled:opacity-50"
        >
          {busy ? "…" : "Deposit"}
        </button>
        <button
          type="button"
          onClick={() => void refresh()}
          className="mb-1 rounded border px-3 py-1.5 text-sm"
        >
          Refresh
        </button>
      </div>

      {acct && (
        <>
          <div className="mt-4 flex items-baseline gap-2">
            <span className="text-2xl font-semibold text-secondary-fixed-dim">{acct.balance}</span>
            <span className="text-sm text-on-surface-variant">USDC unified</span>
          </div>

          <div className="mt-3 flex items-end gap-2">
            <Field label="Spend to (Arc)">
              <input
                value={spendTo}
                onChange={(e) => setSpendTo(e.target.value)}
                className="w-full rounded border border-outline-variant/40 bg-surface-container-lowest text-on-surface placeholder:text-outline px-2 py-1 font-mono text-xs"
              />
            </Field>
            <Field label="Amount">
              <input
                value={spendAmt}
                onChange={(e) => setSpendAmt(e.target.value)}
                className="w-20 rounded border border-outline-variant/40 bg-surface-container-lowest text-on-surface placeholder:text-outline px-2 py-1 font-mono"
              />
            </Field>
            <button
              type="button"
              onClick={() => void spend()}
              disabled={busy || Number(acct.balance) <= 0}
              className="mb-1 rounded border px-3 py-1.5 text-sm disabled:opacity-50"
            >
              Spend
            </button>
          </div>

          {acct.by_chain && Object.keys(acct.by_chain).length > 0 && (
            <ul className="mt-3 space-y-1 text-sm">
              {Object.entries(acct.by_chain).map(([c, amt]) => (
                <li key={c} className="flex justify-between font-mono text-xs">
                  <span className="text-on-surface-variant">{c}</span>
                  <span className="text-secondary-fixed-dim">{amt}</span>
                </li>
              ))}
            </ul>
          )}

          {acct.deposits && acct.deposits.length > 0 && (
            <ul className="mt-3 space-y-1 text-xs">
              {acct.deposits
                .slice()
                .reverse()
                .map((d, i) => (
                  <li key={i} className="flex items-center justify-between gap-2 font-mono">
                    <span className="text-on-surface-variant">
                      +{d.amount} from {d.chain}
                    </span>
                    {d.tx_hash && <TxLink hash={d.tx_hash} prefix="tx" />}
                  </li>
                ))}
            </ul>
          )}
        </>
      )}

      <ErrorNote message={error} />
      {toast}
    </Card>
  );
}
