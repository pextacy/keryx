import { proxyPost } from "@/lib/proxy";

export async function POST(req: Request, ctx: { params: Promise<{ oid: string }> }) {
  const { oid } = await ctx.params;
  return proxyPost(`/order/${encodeURIComponent(oid)}/checkout`, req);
}
