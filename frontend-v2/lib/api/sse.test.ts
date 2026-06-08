import { describe, it, expect, vi } from "vitest";
import { importEventStream } from "./sse";
import type { ImportProgressEvent } from "@/lib/types";

function streamFromChunks(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  let i = 0;
  return new ReadableStream({
    pull(controller) {
      if (i < chunks.length) {
        controller.enqueue(encoder.encode(chunks[i++]));
      } else {
        controller.close();
      }
    },
  });
}

describe("importEventStream", () => {
  it("parse des frames SSE découpées sur plusieurs chunks", async () => {
    const chunks = [
      'data: {"phase":"scraping","mess',
      'age":"x"}\n\n',
      'data: {"phase":"saving","total":40,"imported":20,"skipped":0,"progress":20}\n\n',
      'data: {"phase":"done","imported":40,"skipped":0,"total":40}\n\n',
    ];
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      body: streamFromChunks(chunks),
    } as unknown as Response));

    const events: ImportProgressEvent[] = [];
    for await (const ev of importEventStream("http://x/race")) events.push(ev);

    expect(events.map((e) => e.phase)).toEqual(["scraping", "saving", "done"]);
    expect(events[2]).toMatchObject({ phase: "done", imported: 40 });
    vi.unstubAllGlobals();
  });

  it("lève une erreur si la réponse n'est pas ok", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false } as Response));
    await expect(async () => {
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
      for await (const _ of importEventStream("http://x")) { /* noop */ }
    }).rejects.toThrow();
    vi.unstubAllGlobals();
  });
});
