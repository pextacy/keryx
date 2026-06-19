import { NextRequest, NextResponse } from "next/server";

// Server-side proxy to the agent's /ask (avoids CORS; keeps the agent URL server-only).
const AGENT_URL = process.env.AGENT_URL ?? "http://127.0.0.1:8000";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const resp = await fetch(`${AGENT_URL}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await resp.json();
    return NextResponse.json(data, { status: resp.status });
  } catch (err) {
    return NextResponse.json(
      { error: "agent unreachable", message: (err as Error).message, agent: AGENT_URL },
      { status: 502 },
    );
  }
}
