import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import type { RescrapeProgressEvent } from "@/lib/types";

const { rescrapeEventStream } = vi.hoisted(() => ({
  rescrapeEventStream: vi.fn(),
}));
vi.mock("@/lib/api/sse", () => ({ rescrapeEventStream }));

import { useRescrapeStream } from "./useRescrapeStream";

async function* flux(events: RescrapeProgressEvent[]) {
  for (const event of events) {
    yield event;
  }
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("useRescrapeStream", () => {
  it("passe à `running` dès le déclenchement, avant tout event reçu", () => {
    rescrapeEventStream.mockReturnValue(flux([]));
    const { result } = renderHook(() => useRescrapeStream());

    act(() => {
      result.current.start(42);
    });

    expect(result.current.state.running).toBe(true);
    expect(result.current.state.phase).toBe("scraping");
  });

  it("met à jour phase/progress à chaque event `saving`", async () => {
    rescrapeEventStream.mockReturnValue(
      flux([
        { phase: "saving", total: 10, imported: 2, updated: 1, skipped: 0, progress: 3 },
      ]),
    );
    const { result } = renderHook(() => useRescrapeStream());

    act(() => {
      result.current.start(42);
    });

    await waitFor(() => expect(result.current.state.phase).toBe("saving"));
    expect(result.current.state).toMatchObject({
      total: 10, imported: 2, updated: 1, skipped: 0, progress: 3,
    });
  });

  it("le `done` final expose imported/updated/total/orphans_removed, et arrête `running`", async () => {
    rescrapeEventStream.mockReturnValue(
      flux([
        {
          phase: "done", imported: 3, updated: 7, skipped: 0,
          reconciled: 1, total: 10, orphans_removed: 2,
        },
      ]),
    );
    const { result } = renderHook(() => useRescrapeStream());

    act(() => {
      result.current.start(42);
    });

    await waitFor(() => expect(result.current.state.running).toBe(false));
    expect(result.current.state).toMatchObject({
      phase: "done", imported: 3, updated: 7, total: 10, orphansRemoved: 2,
    });
  });

  it("un event `error` arrête `running` et porte le message", async () => {
    rescrapeEventStream.mockReturnValue(
      flux([{ phase: "error", message: "Le chronométreur n'a publié aucun résultat." }]),
    );
    const { result } = renderHook(() => useRescrapeStream());

    act(() => {
      result.current.start(42);
    });

    await waitFor(() => expect(result.current.state.running).toBe(false));
    expect(result.current.state.phase).toBe("error");
    expect(result.current.state.error).toBe("Le chronométreur n'a publié aucun résultat.");
  });

  it("une exception du flux (409 avant tout octet) arrête `running` avec son message", async () => {
    rescrapeEventStream.mockImplementation(async function* () {
      throw new Error("Un re-scrape est déjà en cours sur cette épreuve.");
    });
    const { result } = renderHook(() => useRescrapeStream());

    act(() => {
      result.current.start(42);
    });

    await waitFor(() => expect(result.current.state.running).toBe(false));
    expect(result.current.state.phase).toBe("error");
    expect(result.current.state.error).toBe("Un re-scrape est déjà en cours sur cette épreuve.");
  });

  it("un second `start` pendant qu'un flux tourne déjà est ignoré", () => {
    rescrapeEventStream.mockReturnValue(flux([]));
    const { result } = renderHook(() => useRescrapeStream());

    act(() => {
      result.current.start(42);
      result.current.start(42);
    });

    expect(rescrapeEventStream).toHaveBeenCalledTimes(1);
  });

  it("reset ramène l'état initial", async () => {
    rescrapeEventStream.mockReturnValue(
      flux([{ phase: "error", message: "boom" }]),
    );
    const { result } = renderHook(() => useRescrapeStream());
    act(() => {
      result.current.start(42);
    });
    await waitFor(() => expect(result.current.state.running).toBe(false));

    act(() => result.current.reset());

    expect(result.current.state.phase).toBe("idle");
    expect(result.current.state.error).toBeNull();
  });
});
