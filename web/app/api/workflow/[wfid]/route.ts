import { proxyGet } from "@/lib/proxy";

export async function GET(_req: Request, ctx: { params: Promise<{ wfid: string }> }) {
  const { wfid } = await ctx.params;
  return proxyGet(`/workflow/${encodeURIComponent(wfid)}`);
}
