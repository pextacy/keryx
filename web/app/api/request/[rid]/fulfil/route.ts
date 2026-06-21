import { proxyPost } from "@/lib/proxy";

export async function POST(req: Request, ctx: { params: Promise<{ rid: string }> }) {
  const { rid } = await ctx.params;
  return proxyPost(`/request/${encodeURIComponent(rid)}/fulfil`, req);
}
