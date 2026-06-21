import { proxyGet } from "@/lib/proxy";

export async function GET(req: Request) {
  const qs = new URL(req.url).search; // forward ?kind=…&limit=… to the agent
  return proxyGet(`/memos${qs}`);
}
