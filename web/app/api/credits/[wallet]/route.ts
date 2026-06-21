import { proxyGet } from "@/lib/proxy";

export async function GET(_req: Request, ctx: { params: Promise<{ wallet: string }> }) {
  const { wallet } = await ctx.params;
  return proxyGet(`/credits/${encodeURIComponent(wallet)}`);
}
