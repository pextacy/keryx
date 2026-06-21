import { proxyPost } from "@/lib/proxy";

export async function POST(req: Request, ctx: { params: Promise<{ wfid: string }> }) {
  const { wfid } = await ctx.params;
  return proxyPost(`/workflow/${encodeURIComponent(wfid)}/execute`, req);
}
