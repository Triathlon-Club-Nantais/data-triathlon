import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiError } from "@/lib/api/client";
import type { CourseBrief } from "@/lib/types";

const { getCourseDeletionImpact, deleteCourse, toastError, toastSuccess } = vi.hoisted(() => ({
  getCourseDeletionImpact: vi.fn(),
  deleteCourse: vi.fn(),
  toastError: vi.fn(),
  toastSuccess: vi.fn(),
}));

vi.mock("sonner", () => ({ toast: { error: toastError, success: toastSuccess } }));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: { getCourseDeletionImpact, deleteCourse },
  };
});

import { DeleteCourseDialog } from "./DeleteCourseDialog";

const EPREUVE: CourseBrief = {
  id: 12,
  name: "Triathlon de Nantes",
  event_date: "2026-05-17",
  event_type: "triathlon-m",
  provider: "klikego",
  source_url: "https://klikego.com/nantes",
  is_relay: false,
};

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <DeleteCourseDialog course={EPREUVE} open onOpenChange={() => {}} />
    </QueryClientProvider>,
  );
}

describe("DeleteCourseDialog", () => {
  beforeEach(() => {
    getCourseDeletionImpact.mockReset();
    deleteCourse.mockReset();
    toastError.mockReset();
    toastSuccess.mockReset();
  });

  it("annonce l'épreuve, ses résultats et les fiches coureur détruites", async () => {
    getCourseDeletionImpact.mockResolvedValue({
      course_id: 12,
      name: "Triathlon de Nantes",
      participations: 412,
      athletes: 37,
    });

    afficher();

    expect(await screen.findByText(/Triathlon de Nantes/)).toBeInTheDocument();
    expect(await screen.findByText(/412/)).toBeInTheDocument();
    expect(await screen.findByText(/37/)).toBeInTheDocument();
  });

  it("n'offre aucune annulation : le geste est irréversible", async () => {
    getCourseDeletionImpact.mockResolvedValue({
      course_id: 12,
      name: "Triathlon de Nantes",
      participations: 3,
      athletes: 0,
    });

    afficher();

    await screen.findByText(/Triathlon de Nantes/);
    expect(screen.queryByRole("button", { name: /annuler la suppression|rétablir|restaurer/i }))
      .not.toBeInTheDocument();
    expect(await screen.findByText(/irréversible/i)).toBeInTheDocument();
  });

  it("supprime après confirmation", async () => {
    getCourseDeletionImpact.mockResolvedValue({
      course_id: 12,
      name: "Triathlon de Nantes",
      participations: 3,
      athletes: 1,
    });
    deleteCourse.mockResolvedValue(null);

    afficher();
    // Le titre s'affiche avant le chiffrage : c'est l'apparition du bouton qui
    // dit que l'impact est connu, et lui seul.
    await userEvent.click(
      await screen.findByRole("button", { name: /supprimer définitivement/i }),
    );

    await waitFor(() => expect(deleteCourse).toHaveBeenCalledWith(12));
  });

  it("dit en français qu'un refus de droits a bloqué la suppression", async () => {
    getCourseDeletionImpact.mockResolvedValue({
      course_id: 12,
      name: "Triathlon de Nantes",
      participations: 3,
      athletes: 0,
    });
    deleteCourse.mockRejectedValue(new ApiError(403, "Vous n'avez pas les droits nécessaires."));

    afficher();
    // Le titre s'affiche avant le chiffrage : c'est l'apparition du bouton qui
    // dit que l'impact est connu, et lui seul.
    await userEvent.click(
      await screen.findByRole("button", { name: /supprimer définitivement/i }),
    );

    await waitFor(() =>
      expect(toastError).toHaveBeenCalledWith("Vous n'avez pas les droits nécessaires."),
    );
    expect(toastSuccess).not.toHaveBeenCalled();
  });

  it("annonce le succès en français, en nommant l'épreuve (FR-019)", async () => {
    getCourseDeletionImpact.mockResolvedValue({
      course_id: 12,
      name: "Triathlon de Nantes",
      participations: 3,
      athletes: 1,
    });
    deleteCourse.mockResolvedValue(null);

    afficher();
    await userEvent.click(
      await screen.findByRole("button", { name: /supprimer définitivement/i }),
    );

    await waitFor(() =>
      expect(toastSuccess).toHaveBeenCalledWith("« Triathlon de Nantes » a été supprimée."),
    );
  });

  it("ne prétend pas connaître l'ampleur quand le chiffrage échoue", async () => {
    getCourseDeletionImpact.mockRejectedValue(new ApiError(500, "Panne"));

    afficher();

    expect(await screen.findByText(/ampleur.*n'a pas pu être|impossible de chiffrer/i))
      .toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /supprimer définitivement/i }))
      .not.toBeInTheDocument();
  });
});
