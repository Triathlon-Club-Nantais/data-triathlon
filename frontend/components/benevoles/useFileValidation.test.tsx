import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import type { AthleteBrief, Participation } from "@/lib/types";

const { getBenevoleQueue, getBenevoleRejected, toastSuccess } = vi.hoisted(() => ({
  getBenevoleQueue: vi.fn(),
  getBenevoleRejected: vi.fn(),
  toastSuccess: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { getBenevoleQueue, getBenevoleRejected } };
});
vi.mock("sonner", () => ({ toast: { success: toastSuccess, error: vi.fn() } }));

import { ApiError } from "@/lib/api/client";
import { useFileValidation } from "./useFileValidation";

const ATHLETE: AthleteBrief = { id: 1, nom: "HERRMANN", prenom: "Mathieu", gender: "M", club: "TCN" };

function participation(id: number, over: Partial<Participation> = {}): Participation {
  return {
    id,
    athlete: ATHLETE,
    course: {
      id: 99,
      name: "Triathlon de Nantes",
      event_date: "2026-06-14",
      event_type: "triathlon",
      provider: "njuko",
      source_url: "https://example.test/r",
      is_relay: false,
    },
    club: "TCN",
    is_tcn: true,
    category: null,
    bib_number: null,
    rank_overall: null,
    rank_category: null,
    rank_gender: null,
    total_time: null,
    status: "finisher",
    is_relay: false,
    splits: null,
    created_at: null,
    is_pending_validation: true,
    ...over,
  };
}

/** Monte le hook avec une file de trois entrées déjà chargée. */
async function monter(file = [participation(1), participation(2), participation(3)]) {
  getBenevoleQueue.mockResolvedValue(file);
  getBenevoleRejected.mockResolvedValue([]);
  const rendu = renderHook(() => useFileValidation());
  await waitFor(() => expect(rendu.result.current.etat).toBe("file"));
  return rendu;
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("useFileValidation", () => {
  it("charge la file et les non conformes", async () => {
    const { result } = await monter();
    expect(result.current.participations).toHaveLength(3);
    expect(result.current.rejetees).toHaveLength(0);
  });

  it("bascule sur la garde d'accès quand l'API répond 401", async () => {
    getBenevoleQueue.mockRejectedValue(new ApiError(401, "non autorisé"));
    getBenevoleRejected.mockRejectedValue(new ApiError(401, "non autorisé"));
    const { result } = renderHook(() => useFileValidation());
    await waitFor(() => expect(result.current.etat).toBe("gate"));
  });

  it("sélectionne l'entrée suivante après une validation", async () => {
    const { result } = await monter();
    act(() => result.current.selectionner(2));
    act(() => result.current.surChangement(participation(2, { is_pending_validation: false })));

    expect(result.current.selectedId).toBe(3);
    expect(result.current.participations.map((p) => p.id)).toEqual([1, 3]);
  });

  it("compte les entrées traitées dans la session", async () => {
    const { result } = await monter();
    expect(result.current.traitees).toBe(0);
    act(() => result.current.surChangement(participation(1, { is_pending_validation: false })));
    act(() => result.current.surChangement(participation(2, { is_rejected: true })));
    expect(result.current.traitees).toBe(2);
  });

  it("annonce le reste de la file après une validation", async () => {
    const { result } = await monter();
    act(() => result.current.surChangement(participation(1, { is_pending_validation: false })));
    expect(toastSuccess).toHaveBeenCalledWith("Résultat validé — 2 restants.");
    expect(result.current.annonce).toBe("Résultat validé — 2 restants.");
  });

  it("laisse la file vide et sans sélection quand la dernière entrée est validée", async () => {
    const { result } = await monter([participation(1)]);
    act(() => result.current.selectionner(1));
    act(() => result.current.surChangement(participation(1, { is_pending_validation: false })));

    expect(result.current.participations).toHaveLength(0);
    expect(result.current.selectedId).toBeNull();
    expect(toastSuccess).toHaveBeenCalledWith("Résultat validé — file vide.");
  });

  it("fait passer une entrée rejetée dans les non conformes et enchaîne", async () => {
    const { result } = await monter();
    act(() => result.current.selectionner(1));
    act(() => result.current.surChangement(participation(1, { is_rejected: true })));

    expect(result.current.participations.map((p) => p.id)).toEqual([2, 3]);
    expect(result.current.rejetees.map((p) => p.id)).toEqual([1]);
    expect(result.current.selectedId).toBe(2);
  });

  it("ne compte ni n'enchaîne sur un simple enregistrement de champs", async () => {
    const { result } = await monter();
    act(() => result.current.selectionner(2));
    act(() => result.current.surChangement(participation(2, { bib_number: "413" })));

    expect(result.current.selectedId).toBe(2);
    expect(result.current.traitees).toBe(0);
    expect(result.current.selectionnee?.bib_number).toBe("413");
  });

  it("ramène une entrée dé-rejetée dans la file sans la compter", async () => {
    getBenevoleQueue.mockResolvedValue([participation(1)]);
    getBenevoleRejected.mockResolvedValue([participation(5, { is_rejected: true })]);
    const { result } = renderHook(() => useFileValidation());
    await waitFor(() => expect(result.current.etat).toBe("file"));

    act(() => result.current.surChangement(participation(5, { is_rejected: false })));

    expect(result.current.participations.map((p) => p.id)).toEqual([5, 1]);
    expect(result.current.rejetees).toHaveLength(0);
    expect(result.current.traitees).toBe(0);
  });
});
