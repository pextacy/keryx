import { NextResponse } from "next/server";

// Server-side proxy to the agent — keeps AGENT_URL server-only and avoids CORS.
const AGENT_URL = process.env.AGENT_URL ?? "http://127.0.0.1:8000";

async function forward(path: string, init?: RequestInit): Promise<NextResponse> {
  try {
    const resp = await fetch(`${AGENT_URL}${path}`, init);
    const data: unknown = await resp.json();
    return NextResponse.json(data, { status: resp.status });
  } catch (err) {
    return NextResponse.json(
      { error: "agent unreachable", message: (err as Error).message, agent: AGENT_URL },
      { status: 502 },
    );
  }
}

export async function proxyGet(path: string): Promise<NextResponse> {
  return forward(path, { method: "GET" });
}

export async function proxyPost(path: string, req: Request): Promise<NextResponse> {
  const body = await req.text();
  return forward(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body || "{}",
  });
}
