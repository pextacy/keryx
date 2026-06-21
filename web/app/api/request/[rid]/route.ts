import { proxyGet } from "@/lib/proxy";

export async function GET(_req: Request, ctx: { params: Promise<{ rid: string }> }) {
  const { rid } = await ctx.params;
  return proxyGet(`/request/${encodeURIComponent(rid)}`);
}
