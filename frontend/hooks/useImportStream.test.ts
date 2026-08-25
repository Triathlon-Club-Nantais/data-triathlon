import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiError } from "@/lib/api/client";
import type { ImportProgressEvent } from "@/lib/types";

const { importEventStream } = vi.hoisted(() => ({ importEventStream: vi.fn() }));
vi.mock("@/lib/api/sse", () => ({ importEventStream }));

import { useImportStream } from "./useImportStream";

async function* flux(events: ImportProgressEvent[]) {
  for (const event of events) yield event;
}

async function* leve(erreur: Error): AsyncGenerator<ImportProgressEvent> {
  throw erreur;
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("useImportStream — la cause de l'échec", () => {
  it("retient le statut HTTP et le délai d'attente d'une ApiError 429", async () => {
    importEventStream.mockReturnValue(leve(new ApiError(429, "Trop de demandes", 180)));
    const { result } = renderHook(() => useImportStream());

    act(() => {
      result.current.start("http://x");
    });

    await waitFor(() => expect(result.current.state.phase).toBe("error"));
    expect(result.current.state.errorStatus).toBe(429);
    expect(result.current.state.retryAfter).toBe(180);
  });

  it("range une coupure réseau en statut 0, sans délai", async () => {
    importEventStream.mockReturnValue(leve(new TypeError("Failed to fetch")));
    const { result } = renderHook(() => useImportStream());

    act(() => {
      result.current.start("http://x");
    });

    await waitFor(() => expect(result.current.state.phase).toBe("error"));
    expect(result.current.state.errorStatus).toBe(0);
    expect(result.current.state.retryAfter).toBeNull();
  });

  it("laisse `errorStatus` nul sur un échec de lecture annoncé par le flux", async () => {
    importEventStream.mockReturnValue(flux([{ phase: "error", message: "Page illisible" }]));
    const { result } = renderHook(() => useImportStream());

    act(() => {
      result.current.start("http://x");
    });

    await waitFor(() => expect(result.current.state.phase).toBe("error"));
    expect(result.current.state.errorStatus).toBeNull();
    expect(result.current.state.error).toBe("Page illisible");
  });
});

describe("useImportStream — annulation", () => {
  it("avorte le flux et revient à l'état initial", async () => {
    const abandon = vi.fn();
    importEventStream.mockImplementation(async function* (_url: string, signal?: AbortSignal) {
      signal?.addEventListener("abort", abandon);
      yield { phase: "scraping", message: "Récupération…" } as ImportProgressEvent;
      await new Promise(() => {});
    });
    const { result } = renderHook(() => useImportStream());

    act(() => {
      result.current.start("http://x");
    });
    await waitFor(() => expect(result.current.state.phase).toBe("scraping"));

    act(() => {
      result.current.cancel();
    });

    await waitFor(() => expect(result.current.state.running).toBe(false));
    expect(result.current.state.phase).toBe("idle");
    expect(abandon).toHaveBeenCalled();
  });

  it("permet de relancer un import après une annulation", async () => {
    importEventStream.mockImplementation(async function* () {
      yield { phase: "scraping", message: "Récupération…" } as ImportProgressEvent;
      await new Promise(() => {});
    });
    const { result } = renderHook(() => useImportStream());

    act(() => {
      result.current.start("http://x");
    });
    await waitFor(() => expect(result.current.state.running).toBe(true));
    act(() => {
      result.current.cancel();
    });
    await waitFor(() => expect(result.current.state.running).toBe(false));

    act(() => {
      result.current.start("http://x");
    });

    await waitFor(() => expect(result.current.state.running).toBe(true));
    expect(importEventStream).toHaveBeenCalledTimes(2);
  });
});

describe("useImportStream — progression phase C Klikego (#583)", () => {
  it("retient detailDone/detailTotal d'un event scraping", async () => {
    importEventStream.mockReturnValue(flux([
      {
        phase: "scraping",
        heat_slug: "triathlon-s-indiv",
        heat_label: "Triathlon S",
        heat_index: 1,
        heats_total: 1,
        detail_done: 10,
        detail_total: 50,
      } as ImportProgressEvent,
    ]));
    const { result } = renderHook(() => useImportStream());

    act(() => {
      result.current.start("http://x");
    });

    await waitFor(() => expect(result.current.state.detailDone).toBe(10));
    expect(result.current.state.detailTotal).toBe(50);
  });

  it("remet detailDone/detailTotal à zéro quand un nouveau heat démarre", async () => {
    importEventStream.mockReturnValue(flux([
      {
        phase: "scraping",
        heat_slug: "triathlon-s-indiv",
        heat_label: "Triathlon S",
        heat_index: 1,
        heats_total: 2,
        detail_done: 40,
        detail_total: 50,
      } as ImportProgressEvent,
      {
        phase: "scraping",
        heat_slug: "swim-run-m-duo",
        heat_label: "SwimRun M duo",
        heat_index: 2,
        heats_total: 2,
      } as ImportProgressEvent,
    ]));
    const { result } = renderHook(() => useImportStream());

    act(() => {
      result.current.start("http://x");
    });

    await waitFor(() => expect(result.current.state.heatIndex).toBe(2));
    expect(result.current.state.detailDone).toBe(0);
    expect(result.current.state.detailTotal).toBe(0);
  });
});
