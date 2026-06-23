import { NextRequest, NextResponse } from "next/server";

// Server-side proxy to the agent's /ask (avoids CORS; keeps the agent URL server-only).
const AGENT_URL = process.env.AGENT_URL ?? "http://127.0.0.1:8000";
const API_TOKEN = process.env.KERYX_API_TOKEN ?? "";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (API_TOKEN) headers["Authorization"] = `Bearer ${API_TOKEN}`;
    const resp = await fetch(`${AGENT_URL}/ask`, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
    });
    const data = await resp.json();
    return NextResponse.json(data, { status: resp.status });
  } catch (err) {
    // Don't leak the internal agent host to the browser — just the failure.
    return NextResponse.json(
      { error: "agent unreachable", message: (err as Error).message },
      { status: 502 },
    );
  }
}
