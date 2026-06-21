import { proxyGet } from "@/lib/proxy";

export async function GET(req: Request) {
  const qs = new URL(req.url).search; // forward ?kind=…&limit=…
  return proxyGet(`/history${qs}`);
}
