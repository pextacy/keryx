"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { errorMessage, postJson } from "@/lib/api";
import type { StreamResponse } from "@/lib/capabilities";
import { Card, ErrorNote, Field } from "./Card";

export function StreamPanel() {
  const [payer, setPayer] = useState("0x" + "1".repeat(40));
  const [payee, setPayee] = useState("0x" + "2".repeat(40));
  const [rate, setRate] = useState("0.001");
  const [seconds, setSeconds] = useState("3");
  const [stream, setStream] = useState<StreamResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [live, setLive] = useState(false);
  const streamId = stream?.stream_id ?? null;

  async function run(fn: () => Promise<StreamResponse>) {
    setBusy(true);
    setError(null);
    try {
      setStream(await fn());
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  const open = () => run(() => postJson<StreamResponse>("/api/stream", { payer, payee, rate }));

  const action = (a: "tick" | "pause" | "resume" | "close") => {
    if (!stream) return;
    if (a === "close") setLive(false);
    const id = encodeURIComponent(stream.stream_id);
    const body = a === "tick" ? { seconds } : {};
    void run(() => postJson<StreamResponse>(`/api/stream/${id}/${a}`, body));
  };

  // Live meter: tick 1 second of flow every second while "live" is on.
  const tickOnce = useCallback(async () => {
    if (!streamId) return;
    try {
      const next = await postJson<StreamResponse>(`/api/stream/${encodeURIComponent(streamId)}/tick`, {
        seconds: "1",
      });
      setStream(next);
    } catch (err) {
      setError(errorMessage(err));
      setLive(false);
    }
  }, [streamId]);

  const liveRef = useRef(tickOnce);
  liveRef.current = tickOnce;
  useEffect(() => {
    if (!live || !streamId) return;
    const handle = setInterval(() => void liveRef.current(), 1000);
    return () => clearInterval(handle);
  }, [live, streamId]);

  return (
    <Card title="Streaming" subtitle="Pay-per-second flow, billed live with no dust (RFB 4)">
      <div className="grid grid-cols-2 gap-2">
        <Field label="Payer">
          <input
            value={payer}
            onChange={(e) => setPayer(e.target.value)}
            className="w-full rounded border border-outline-variant/40 bg-surface-container-lowest text-on-surface placeholder:text-outline px-2 py-1 font-mono text-xs"
          />
        </Field>
        <Field label="Payee">
          <input
            value={payee}
            onChange={(e) => setPayee(e.target.value)}
            className="w-full rounded border border-outline-variant/40 bg-surface-container-lowest text-on-surface placeholder:text-outline px-2 py-1 font-mono text-xs"
          />
        </Field>
        <Field label="Rate (USDC/s)">
          <input
            value={rate}
            onChange={(e) => setRate(e.target.value)}
            className="w-full rounded border border-outline-variant/40 bg-surface-container-lowest text-on-surface placeholder:text-outline px-2 py-1 font-mono"
          />
        </Field>
        <Field label="Tick seconds">
          <input
            value={seconds}
            onChange={(e) => setSeconds(e.target.value)}
            className="w-full rounded border border-outline-variant/40 bg-surface-container-lowest text-on-surface placeholder:text-outline px-2 py-1 font-mono"
          />
        </Field>
      </div>

      <div className="mt-4 flex flex-wrap gap-2 text-sm">
        <button type="button" onClick={open} disabled={busy} className="rounded bg-primary-fixed-dim px-3 py-1.5 text-on-primary-fixed font-bold disabled:opacity-50">
          Open
        </button>
        <button type="button" onClick={() => action("tick")} disabled={busy || !stream} className="rounded border px-3 py-1.5 disabled:opacity-40">
          Tick
        </button>
        <button type="button" onClick={() => action("pause")} disabled={busy || !stream} className="rounded border px-3 py-1.5 disabled:opacity-40">
          Pause
        </button>
        <button type="button" onClick={() => action("resume")} disabled={busy || !stream} className="rounded border px-3 py-1.5 disabled:opacity-40">
          Resume
        </button>
        <button type="button" onClick={() => action("close")} disabled={busy || !stream} className="rounded border px-3 py-1.5 disabled:opacity-40">
          Close
        </button>
        <button
          type="button"
          onClick={() => setLive((v) => !v)}
          disabled={!stream}
          className={`rounded px-3 py-1.5 disabled:opacity-40 ${live ? "bg-secondary-fixed-dim text-white" : "border"}`}
        >
          {live ? "● Live" : "Go live (1/s)"}
        </button>
      </div>

      <ErrorNote message={error} />

      {stream && (
        <dl className="mt-4 space-y-1 font-mono text-sm">
          <div className="flex justify-between">
            <span className="text-on-surface-variant">stream</span>
            <span>{stream.stream_id}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-on-surface-variant">status</span>
            <span>{stream.status}</span>
          </div>
          {stream.billed !== undefined && (
            <div className="flex justify-between">
              <span className="text-on-surface-variant">last billed</span>
              <span>{stream.billed}</span>
            </div>
          )}
          <div className="flex justify-between text-secondary-fixed-dim">
            <span>total settled</span>
            <span>{stream.total_settled} USDC</span>
          </div>
        </dl>
      )}
    </Card>
  );
}
