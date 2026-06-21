import { proxyPost } from "@/lib/proxy";

export async function POST(req: Request, ctx: { params: Promise<{ sid: string }> }) {
  const { sid } = await ctx.params;
  return proxyPost(`/schedule/${encodeURIComponent(sid)}/cancel`, req);
}
