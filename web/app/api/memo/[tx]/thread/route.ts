import { proxyGet } from "@/lib/proxy";

export async function GET(_req: Request, ctx: { params: Promise<{ tx: string }> }) {
  const { tx } = await ctx.params;
  return proxyGet(`/memo/${encodeURIComponent(tx)}/thread`);
}
