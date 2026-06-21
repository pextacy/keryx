"use client";

import { useState } from "react";
import { errorMessage, getJson, postJson } from "@/lib/api";
import type { GatewayResponse } from "@/lib/capabilities";
import { useToast } from "@/app/Toast";
import { Card, ErrorNote, Field } from "./Card";
import { TxLink } from "./TxLink";

const CHAINS = ["arcTestnet", "avalancheFuji", "baseSepolia"] as const;

// Gateway unified balance (ported from arc-multichain-wallet): deposit USDC from several
// source chains into one Arc-spendable balance, with per-chain provenance.
export function GatewayPanel() {
  const { toast, notify } = useToast();
  const [wallet, setWallet] = useState("0x" + "a".repeat(40));
  const [chain, setChain] = useState<(typeof CHAINS)[number]>("avalancheFuji");
  const [amount, setAmount] = useState("0.5");
  const [spendTo, setSpendTo] = useState("0x" + "c".repeat(40));
  const [spendAmt, setSpendAmt] = useState("0.2");
  const [destChain, setDestChain] = useState<(typeof CHAINS)[number]>("baseSepolia");
  const [xferAmt, setXferAmt] = useState("0.1");
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

  async function transfer() {
    setBusy(true);
    setError(null);
    try {
      const r = await postJson<GatewayResponse>("/api/gateway/transfer", {
        wallet,
        destination_chain: destChain,
        amount: xferAmt,
      });
      if (r.error) setError(r.error);
      else {
        setAcct(r);
        if (r.transferred) notify(`Transferred ${r.amount} to ${r.destination_chain}`, r.tx_hash);
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
      subtitle="Deposit from many chains, spend on Arc, or transfer back out cross-chain (multichain-wallet)"
    >
      <Field label="Wallet">
        <input
          value={wallet}
          onChange={(e) => setWallet(e.target.value)}
          className="w-full rounded border border-gray-300 px-2 py-1 font-mono text-xs"
        />
      </Field>

      <div className="mt-3 flex items-end gap-2">
        <Field label="Source chain">
          <select
            value={chain}
            onChange={(e) => setChain(e.target.value as (typeof CHAINS)[number])}
            className="rounded border border-gray-300 px-2 py-1 text-sm"
          >
            {CHAINS.map((ch) => (
              <option key={ch}>{ch}</option>
            ))}
          </select>
        </Field>
        <Field label="Amount">
          <input
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            className="w-24 rounded border border-gray-300 px-2 py-1 font-mono"
          />
        </Field>
        <button
          type="button"
          onClick={() => void deposit()}
          disabled={busy}
          className="mb-1 rounded bg-black px-3 py-1.5 text-sm text-white disabled:opacity-50"
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
            <span className="text-2xl font-semibold text-green-700">{acct.balance}</span>
            <span className="text-sm text-gray-500">USDC unified</span>
          </div>

          <div className="mt-3 flex items-end gap-2">
            <Field label="Spend to (Arc)">
              <input
                value={spendTo}
                onChange={(e) => setSpendTo(e.target.value)}
                className="w-full rounded border border-gray-300 px-2 py-1 font-mono text-xs"
              />
            </Field>
            <Field label="Amount">
              <input
                value={spendAmt}
                onChange={(e) => setSpendAmt(e.target.value)}
                className="w-20 rounded border border-gray-300 px-2 py-1 font-mono"
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

          <div className="mt-3 flex items-end gap-2">
            <Field label="Transfer to chain">
              <select
                value={destChain}
                onChange={(e) => setDestChain(e.target.value as (typeof CHAINS)[number])}
                className="rounded border border-gray-300 px-2 py-1 text-sm"
              >
                {CHAINS.map((ch) => (
                  <option key={ch}>{ch}</option>
                ))}
              </select>
            </Field>
            <Field label="Amount">
              <input
                value={xferAmt}
                onChange={(e) => setXferAmt(e.target.value)}
                className="w-20 rounded border border-gray-300 px-2 py-1 font-mono"
              />
            </Field>
            <button
              type="button"
              onClick={() => void transfer()}
              disabled={busy || Number(acct.balance) <= 0}
              className="mb-1 rounded border px-3 py-1.5 text-sm disabled:opacity-50"
            >
              Transfer
            </button>
          </div>

          {acct.by_chain && Object.keys(acct.by_chain).length > 0 && (
            <ul className="mt-3 space-y-1 text-sm">
              {Object.entries(acct.by_chain).map(([c, amt]) => (
                <li key={c} className="flex justify-between font-mono text-xs">
                  <span className="text-gray-600">{c}</span>
                  <span className="text-green-700">{amt}</span>
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
                    <span className="text-gray-500">
                      +{d.amount} from {d.chain}
                    </span>
                    {d.tx_hash && <TxLink hash={d.tx_hash} prefix="tx" />}
                  </li>
                ))}
            </ul>
          )}

          {acct.withdrawals && acct.withdrawals.length > 0 && (
            <ul className="mt-2 space-y-1 text-xs">
              {acct.withdrawals
                .slice()
                .reverse()
                .map((w, i) => (
                  <li key={i} className="flex items-center justify-between gap-2 font-mono">
                    <span className="text-gray-500">
                      −{w.amount} to {w.chain}
                    </span>
                    {w.tx_hash && <TxLink hash={w.tx_hash} prefix="tx" />}
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
