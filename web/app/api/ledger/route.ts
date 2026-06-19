import { NextResponse } from "next/server";

const AGENT_URL = process.env.AGENT_URL ?? "http://127.0.0.1:8000";

export async function GET() {
  try {
    const resp = await fetch(`${AGENT_URL}/ledger`, { cache: "no-store" });
    const data = await resp.json();
    return NextResponse.json(data, { status: resp.status });
  } catch (err) {
    return NextResponse.json(
      { error: "agent unreachable", message: (err as Error).message },
      { status: 502 },
    );
  }
}
