import { proxyGet } from "@/lib/proxy";

export async function GET(req: Request) {
  const limit = new URL(req.url).searchParams.get("limit");
  return proxyGet(`/ledger${limit ? `?limit=${encodeURIComponent(limit)}` : ""}`);
}
