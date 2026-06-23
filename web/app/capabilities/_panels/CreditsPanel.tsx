"use client";

import { useEffect, useState } from "react";
import { errorMessage, getJson, postJson } from "@/lib/api";
import type { CreditsResponse, CreditTier } from "@/lib/capabilities";
import { useToast } from "@/app/Toast";
import { Card, ErrorNote, Field } from "./Card";
import { TxLink } from "./TxLink";

// Prepaid credits (ported from arc-commerce): top up USDC once into a balance, then draw it
// down per action. A tier grants bonus credits per USDC (bulk discount); top-up settles to the
// treasury (fires the toast); spends are pure draws.
export function CreditsPanel() {
  const { toast, notify } = useToast();
  const [wallet, setWallet] = useState("0x" + "a".repeat(40));
  const [topup, setTopup] = useState("0.05");
  const [tier, setTier] = useState("");
  const [tiers, setTiers] = useState<CreditTier[]>([]);
  const [spend, setSpend] = useState("0.001");
  const [reason, setReason] = useState("citation");
  const [acct, setAcct] = useState<CreditsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getJson<{ tiers: CreditTier[] }>("/api/credits/tiers")
      .then((r) => setTiers(r.tiers))
      .catch(() => {});
  }, []);

  async function doTopup() {
    setBusy(true);
    setError(null);
    try {
      const body = tier ? { wallet, tier } : { wallet, amount: topup };
      const r = await postJson<CreditsResponse>("/api/credits/topup", body);
      if (r.error) setError(r.error);
      else {
        setAcct(r);
        if (r.topped_up) notify(`Topped up ${r.credited ?? topup} credits`, r.tx_hash);
      }
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function doSpend() {
    setError(null);
    try {
      const r = await postJson<CreditsResponse>("/api/credits/spend", {
        wallet,
        amount: spend,
        reason,
      });
      if (r.error) setError(r.error);
      else setAcct(r);
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function refresh() {
    setError(null);
    try {
      setAcct(await getJson<CreditsResponse>(`/api/credits/${encodeURIComponent(wallet)}`));
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <Card
      title="Prepaid credits (commerce)"
      subtitle="Top up USDC once, then draw it down per action — one settlement funds many tolls"
    >
      <Field label="Wallet">
        <input
          value={wallet}
          onChange={(e) => setWallet(e.target.value)}
          className="w-full rounded border border-outline-variant/40 bg-surface-container-lowest text-on-surface placeholder:text-outline px-2 py-1 font-mono text-xs"
        />
      </Field>

      <div className="mt-3 flex items-end gap-2">
        <Field label="Package">
          <select
            value={tier}
            onChange={(e) => setTier(e.target.value)}
            className="rounded border border-outline-variant/40 bg-surface-container-lowest text-on-surface placeholder:text-outline px-2 py-1 text-sm"
          >
            <option value="">custom</option>
            {tiers.map((t) => (
              <option key={t.name} value={t.name}>
                {t.name}: {t.usdc} → {t.credits}
                {t.bonus_bps > 0 ? ` (+${t.bonus_bps / 100}%)` : ""}
              </option>
            ))}
          </select>
        </Field>
        {!tier && (
          <Field label="Top up (USDC)">
            <input
              value={topup}
              onChange={(e) => setTopup(e.target.value)}
              className="w-24 rounded border border-outline-variant/40 bg-surface-container-lowest text-on-surface placeholder:text-outline px-2 py-1 font-mono"
            />
          </Field>
        )}
        <button
          type="button"
          onClick={() => void doTopup()}
          disabled={busy}
          className="mb-1 rounded bg-primary-fixed-dim px-3 py-1.5 text-sm text-on-primary-fixed font-bold disabled:opacity-50"
        >
          {busy ? "…" : "Top up"}
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
            <span className="text-sm text-on-surface-variant">credits (USDC)</span>
          </div>

          <div className="mt-3 flex items-end gap-2">
            <Field label="Spend">
              <input
                value={spend}
                onChange={(e) => setSpend(e.target.value)}
                className="w-24 rounded border border-outline-variant/40 bg-surface-container-lowest text-on-surface placeholder:text-outline px-2 py-1 font-mono"
              />
            </Field>
            <Field label="Reason">
              <input
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                className="w-32 rounded border border-outline-variant/40 bg-surface-container-lowest text-on-surface placeholder:text-outline px-2 py-1 text-sm"
              />
            </Field>
            <button
              type="button"
              onClick={() => void doSpend()}
              className="mb-1 rounded border px-3 py-1.5 text-sm"
            >
              Draw down
            </button>
          </div>

          {acct.entries && acct.entries.length > 0 && (
            <ul className="mt-4 space-y-1 text-xs">
              {acct.entries
                .slice()
                .reverse()
                .map((e, i) => (
                  <li key={i} className="flex items-center justify-between gap-2 font-mono">
                    <span
                      className={
                        e.kind === "topup" ? "text-secondary-fixed-dim" : "text-on-surface-variant"
                      }
                    >
                      {e.kind === "topup" ? "+" : "−"}
                      {e.amount} · {e.reason}
                    </span>
                    {e.tx_hash ? (
                      <TxLink hash={e.tx_hash} prefix="tx" />
                    ) : (
                      <span className="text-outline">draw</span>
                    )}
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
