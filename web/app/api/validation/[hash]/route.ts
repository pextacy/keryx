import { proxyGet } from "@/lib/proxy";

export async function GET(_req: Request, ctx: { params: Promise<{ hash: string }> }) {
  const { hash } = await ctx.params;
  return proxyGet(`/validation/${encodeURIComponent(hash)}`);
}
