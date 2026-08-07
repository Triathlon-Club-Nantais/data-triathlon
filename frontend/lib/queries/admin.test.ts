import { QueryClient } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { createElement, type ReactNode } from "react";
import { QueryClientProvider } from "@tanstack/react-query";

const { updateAthlete, reassignParticipation, updateCourse, deleteCourse } = vi.hoisted(() => ({
  updateAthlete: vi.fn(),
  reassignParticipation: vi.fn(),
  updateCourse: vi.fn(),
  deleteCourse: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: { updateAthlete, reassignParticipation, updateCourse, deleteCourse },
  };
});

import {
  useUpdateAthlete,
  useUpdateCourse,
  useDeleteCourse,
  useReassignParticipation,
} from "./admin";

/**
 * Les quatre gestes périment le cache des résultats d'une épreuve.
 *
 * C'est celui que lit `CourseParticipationsDialog`, et il est servi par
 * `apiClient.getCourse` — donc aucune des clés « évidentes » d'un geste ne le
 * touche. Sans invalidation, corriger un coureur laisse son ancien nom affiché
 * dans la liste d'où l'on vient de le corriger.
 */
let client: QueryClient;

function wrapper({ children }: { children: ReactNode }) {
  return createElement(QueryClientProvider, { client }, children);
}

describe("invalidations des gestes d'administration", () => {
  beforeEach(() => {
    client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    updateAthlete.mockResolvedValue({});
    reassignParticipation.mockResolvedValue({});
    updateCourse.mockResolvedValue({});
    deleteCourse.mockResolvedValue(undefined);
  });

  const gestes = [
    {
      nom: "corriger un coureur",
      hook: useUpdateAthlete,
      declencher: (mutate: (v: never) => void) =>
        mutate({ id: 1, champs: { nom: "Dupont" } } as never),
    },
    {
      nom: "rattacher un résultat",
      hook: useReassignParticipation,
      declencher: (mutate: (v: never) => void) =>
        mutate({ participationId: 7, athleteId: 2 } as never),
    },
    {
      nom: "corriger une épreuve",
      hook: useUpdateCourse,
      declencher: (mutate: (v: never) => void) =>
        mutate({ id: 12, champs: { name: "X" } } as never),
    },
    {
      nom: "supprimer une épreuve",
      hook: useDeleteCourse,
      declencher: (mutate: (v: never) => void) => mutate(12 as never),
    },
  ];

  it.each(gestes)("$nom périme le détail admin d'une épreuve", async ({ hook, declencher }) => {
    const invalider = vi.spyOn(client, "invalidateQueries");
    const { result } = renderHook(() => hook(), { wrapper });

    declencher(result.current.mutate as (v: never) => void);

    await waitFor(() =>
      expect(invalider).toHaveBeenCalledWith({ queryKey: ["admin-course-detail"] }),
    );
  });
});
