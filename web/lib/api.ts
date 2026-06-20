// Typed client helpers for calling the Next API proxies. Narrow errors to a message.

async function unwrap<T>(r: Response): Promise<T> {
  const data: unknown = await r.json();
  if (!r.ok) {
    const d = data as { message?: string; error?: string };
    throw new Error(d.message ?? d.error ?? `request failed (${r.status})`);
  }
  return data as T;
}

export async function postJson<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return unwrap<T>(r);
}

export async function getJson<T>(path: string): Promise<T> {
  return unwrap<T>(await fetch(path));
}

export function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : "Unexpected error";
}
