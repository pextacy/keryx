import { proxyPost } from "@/lib/proxy";

export async function POST(req: Request) {
  return proxyPost("/escrow", req);
}
