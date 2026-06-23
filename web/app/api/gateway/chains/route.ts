import { proxyGet } from "@/lib/proxy";

// Static segment — takes precedence over the sibling [wallet] dynamic route for /api/gateway/chains.
export async function GET() {
  return proxyGet("/gateway/chains");
}
