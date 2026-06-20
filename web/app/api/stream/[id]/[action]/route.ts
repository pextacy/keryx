import { proxyPost } from "@/lib/proxy";

// Handles POST /stream/{id}/{tick|pause|resume|close}.
export async function POST(req: Request, ctx: { params: Promise<{ id: string; action: string }> }) {
  const { id, action } = await ctx.params;
  return proxyPost(`/stream/${encodeURIComponent(id)}/${encodeURIComponent(action)}`, req);
}
