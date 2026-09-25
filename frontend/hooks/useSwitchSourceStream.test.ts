import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import type { SwitchSourceProgressEvent } from "@/lib/types";

const { switchSourceEventStream } = vi.hoisted(() => ({ switchSourceEventStream: vi.fn() }));
vi.mock("@/lib/api/sse", () => ({ switchSourceEventStream }));

import { useSwitchSourceStream } from "./useSwitchSourceStream";

async function* flux(events: SwitchSourceProgressEvent[]) {
  for (const event of events) yield event;
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("useSwitchSourceStream", () => {
  it("passe en erreur de coupure quand le flux se ferme sans done ni error (#985)", async () => {
    switchSourceEventStream.mockReturnValue(flux([{ phase: "saving", total: 10 }]));
    const { result } = renderHook(() => useSwitchSourceStream());

    let resultat: Awaited<ReturnType<typeof result.current.start>> = null;
    await act(async () => {
      resultat = await result.current.start(42, 2);
    });

    const message = "Connexion interrompue avant la fin de la bascule. Rechargez la page pour vérifier les résultats.";
    expect(resultat).toEqual({ phase: "error", message });
    await waitFor(() => expect(result.current.state.phase).toBe("error"));
    expect(result.current.state.running).toBe(false);
    expect(result.current.state.error).toBe(message);
  });
});
