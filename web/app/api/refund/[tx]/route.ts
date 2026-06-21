import { proxyPost } from "@/lib/proxy";

export async function POST(req: Request, ctx: { params: Promise<{ tx: string }> }) {
  const { tx } = await ctx.params;
  return proxyPost(`/refund/${encodeURIComponent(tx)}`, req);
}
