import { NextResponse } from "next/server";

// Server-side proxy to the agent — keeps AGENT_URL server-only and avoids CORS.
// Render's `fromService` injects a hostname only, so prepend https:// when no scheme is given.
const RAW_AGENT_URL = process.env.AGENT_URL ?? "http://127.0.0.1:8000";
const AGENT_URL = /^https?:\/\//.test(RAW_AGENT_URL) ? RAW_AGENT_URL : `https://${RAW_AGENT_URL}`;

async function forward(path: string, init?: RequestInit): Promise<NextResponse> {
  try {
    const headers = new Headers(init?.headers);
    // Forward auth to the agent's protected settlement endpoints when configured.
    const apiKey = process.env.AGENT_API_KEY;
    if (apiKey) headers.set("X-API-Key", apiKey);
    const resp = await fetch(`${AGENT_URL}${path}`, { ...init, headers });
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
