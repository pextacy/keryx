import { proxyGet } from "@/lib/proxy";

export async function GET(_req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  return proxyGet(`/circle/transaction/${encodeURIComponent(id)}`);
}
