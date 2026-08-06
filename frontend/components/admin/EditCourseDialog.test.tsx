import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiError } from "@/lib/api/client";
import type { CourseBrief } from "@/lib/types";

const { updateCourse, toastError, toastSuccess } = vi.hoisted(() => ({
  updateCourse: vi.fn(),
  toastError: vi.fn(),
  toastSuccess: vi.fn(),
}));

vi.mock("sonner", () => ({ toast: { error: toastError, success: toastSuccess } }));
vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { updateCourse } };
});

import { EditCourseDialog } from "./EditCourseDialog";

const EPREUVE: CourseBrief = {
  id: 12,
  name: "Tri de Nates",
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
      <EditCourseDialog course={EPREUVE} open onOpenChange={() => {}} />
    </QueryClientProvider>,
  );
}

describe("EditCourseDialog", () => {
  beforeEach(() => {
    updateCourse.mockReset();
    toastError.mockReset();
    toastSuccess.mockReset();
  });

  it("propose les quatre champs de l'identité de l'épreuve", () => {
    afficher();

    expect(screen.getByLabelText(/nom/i)).toHaveValue("Tri de Nates");
    expect(screen.getByLabelText(/date/i)).toHaveValue("2026-05-17");
    expect(screen.getByLabelText(/type/i)).toHaveValue("triathlon-m");
    expect(screen.getByLabelText(/relais/i)).toBeInTheDocument();
  });

  it("enregistre la correction", async () => {
    updateCourse.mockResolvedValue(EPREUVE);

    afficher();
    const nom = screen.getByLabelText(/nom/i);
    await userEvent.clear(nom);
    await userEvent.type(nom, "Triathlon de Nantes");
    await userEvent.click(screen.getByRole("button", { name: /enregistrer/i }));

    await waitFor(() =>
      expect(updateCourse).toHaveBeenCalledWith(
        12,
        expect.objectContaining({ name: "Triathlon de Nantes" }),
      ),
    );
  });

  it("montre en français l'épreuve en conflit", async () => {
    updateCourse.mockRejectedValue(
      new ApiError(409, "Une épreuve porte déjà ce nom à cette date (fiche #7)."),
    );

    afficher();
    await userEvent.click(screen.getByRole("button", { name: /enregistrer/i }));

    await waitFor(() =>
      expect(toastError).toHaveBeenCalledWith(
        "Une épreuve porte déjà ce nom à cette date (fiche #7).",
      ),
    );
  });
});
