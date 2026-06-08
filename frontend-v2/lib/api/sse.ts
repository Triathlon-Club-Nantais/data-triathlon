import type { ImportProgressEvent } from "@/lib/types";

const BASE = "/api/v1";

export async function* importEventStream(
  url: string,
): AsyncGenerator<ImportProgressEvent> {
  const res = await fetch(`${BASE}/scrape/event/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
  if (!res.ok || !res.body) {
    throw new Error("Erreur lors du démarrage de l'import");
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const parts = buf.split("\n\n");
    buf = parts.pop() ?? "";
    for (const part of parts) {
      if (part.startsWith("data: ")) {
        try {
          yield JSON.parse(part.slice(6)) as ImportProgressEvent;
        } catch {
          /* frame incomplète ou bruit : ignorer */
        }
      }
    }
  }
}
