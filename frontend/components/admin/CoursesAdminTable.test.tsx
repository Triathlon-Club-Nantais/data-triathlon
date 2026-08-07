import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiError } from "@/lib/api/client";
import type { CourseBrief, SessionUser } from "@/lib/types";

const { listCourses, getSession } = vi.hoisted(() => ({
  listCourses: vi.fn(),
  getSession: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: { listCourses, getSession },
  };
});

import { CoursesAdminTable } from "./CoursesAdminTable";

const EPREUVE: CourseBrief = {
  id: 12,
  name: "Triathlon de Nantes",
  event_date: "2026-05-17",
  event_type: "triathlon-m",
  provider: "klikego",
  source_url: "https://klikego.com/nantes",
  is_relay: false,
};

function session(permissions: string[]): SessionUser {
  return {
    id: 1,
    email: "admin@exemple.fr",
    display_name: "Admin",
    created_at: "2026-01-01T00:00:00Z",
    permissions,
    roles: [],
  };
}

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <CoursesAdminTable />
    </QueryClientProvider>,
  );
}

describe("CoursesAdminTable", () => {
  beforeEach(() => {
    listCourses.mockReset();
    getSession.mockReset();
    getSession.mockResolvedValue(session([]));
  });

  it("liste les épreuves", async () => {
    listCourses.mockResolvedValue([EPREUVE]);

    afficher();

    expect(await screen.findByText("Triathlon de Nantes")).toBeInTheDocument();
    // La colonne Type porte un libellé, pas le slug de base.
    expect(screen.getByText("Triathlon M")).toBeInTheDocument();
    expect(screen.queryByText("triathlon-m")).not.toBeInTheDocument();
  });

  it("cache le bouton de suppression sans le pouvoir (FR-011)", async () => {
    listCourses.mockResolvedValue([EPREUVE]);
    getSession.mockResolvedValue(session([]));

    afficher();

    await screen.findByText("Triathlon de Nantes");
    expect(screen.queryByRole("button", { name: /supprimer/i })).not.toBeInTheDocument();
  });

  it("offre la suppression à qui porte courses:delete", async () => {
    listCourses.mockResolvedValue([EPREUVE]);
    getSession.mockResolvedValue(session(["courses:delete"]));

    afficher();

    expect(await screen.findByRole("button", { name: /supprimer/i })).toBeInTheDocument();
  });

  it("nomme chaque geste par son épreuve — les icônes seules sont muettes", async () => {
    listCourses.mockResolvedValue([EPREUVE, { ...EPREUVE, id: 13, name: "Triathlon de Vertou" }]);
    getSession.mockResolvedValue(session(["courses:delete", "courses:write"]));

    afficher();

    // Sans le nom dans le libellé, une page en aligne cinquante « Supprimer »
    // que rien ne distingue à la lecture d'écran.
    expect(
      await screen.findByRole("button", { name: "Supprimer — Triathlon de Vertou" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Corriger — Triathlon de Nantes" }),
    ).toBeInTheDocument();
  });

  it("distingue une panne d'une liste vide", async () => {
    listCourses.mockRejectedValue(new ApiError(500, "Panne"));

    afficher();

    expect(await screen.findByText(/indisponible/i)).toBeInTheDocument();
    expect(screen.queryByText(/aucune épreuve/i)).not.toBeInTheDocument();
  });

  it("dit « aucune épreuve » seulement quand la liste est réellement vide", async () => {
    listCourses.mockResolvedValue([]);

    afficher();

    expect(await screen.findByText(/aucune épreuve/i)).toBeInTheDocument();
  });

  it("permet d'atteindre la page suivante — la base en compte 211", async () => {
    // Sans pagination, tout ce qui dépasse la 50ᵉ épreuve est inatteignable
    // depuis le back-office, donc ni corrigeable ni supprimable (SC-001).
    listCourses.mockResolvedValue(
      Array.from({ length: 50 }, (_, i) => ({ ...EPREUVE, id: i + 1, name: `Épreuve ${i + 1}` })),
    );

    afficher();
    await screen.findByText("Épreuve 1");
    await userEvent.click(screen.getByRole("button", { name: /suivante/i }));

    await waitFor(() =>
      expect(listCourses).toHaveBeenCalledWith(expect.objectContaining({ page: 2 })),
    );
  });

  it("n'offre pas de page suivante sur une dernière page incomplète", async () => {
    listCourses.mockResolvedValue([EPREUVE]);

    afficher();
    await screen.findByText("Triathlon de Nantes");

    expect(screen.getByRole("button", { name: /suivante/i })).toBeDisabled();
  });

  it("n'offre pas de page précédente sur la première page", async () => {
    listCourses.mockResolvedValue([EPREUVE]);

    afficher();
    await screen.findByText("Triathlon de Nantes");

    expect(screen.getByRole("button", { name: /précédente/i })).toBeDisabled();
  });
});
