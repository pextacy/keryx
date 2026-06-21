import { proxyPost } from "@/lib/proxy";

export async function POST(req: Request, ctx: { params: Promise<{ eid: string }> }) {
  const { eid } = await ctx.params;
  return proxyPost(`/escrow/${encodeURIComponent(eid)}/release`, req);
}
