import { NextResponse } from "next/server";

// Server-side proxy to the agent — keeps AGENT_URL server-only and avoids CORS.
const AGENT_URL = process.env.AGENT_URL ?? "http://127.0.0.1:8000";
// Forwarded to the agent when KERYX_API_TOKEN is set there too; empty in the local demo.
const API_TOKEN = process.env.KERYX_API_TOKEN ?? "";

async function forward(path: string, init?: RequestInit): Promise<NextResponse> {
  const headers = new Headers(init?.headers);
  if (API_TOKEN) headers.set("Authorization", `Bearer ${API_TOKEN}`);
  try {
    const resp = await fetch(`${AGENT_URL}${path}`, { ...init, headers });
    const data: unknown = await resp.json();
    return NextResponse.json(data, { status: resp.status });
  } catch (err) {
    // Don't leak the internal agent host to the browser — just the failure.
    return NextResponse.json(
      { error: "agent unreachable", message: (err as Error).message },
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
