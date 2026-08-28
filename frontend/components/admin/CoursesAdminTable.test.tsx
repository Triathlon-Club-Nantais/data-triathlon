import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiError } from "@/lib/api/client";
import type { CourseBrief, SessionUser } from "@/lib/types";

const { listCourses, countCourses, getSession } = vi.hoisted(() => ({
  listCourses: vi.fn(),
  countCourses: vi.fn(),
  getSession: vi.fn(),
}));

const push = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
  usePathname: () => "/admin/courses",
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: { listCourses, countCourses, getSession },
  };
});

import { TAILLE_PAGE_ADMIN } from "@/lib/queries/admin";
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

/** Une tranche pleine — donc suivie d'au moins une autre. */
function pleine(): CourseBrief[] {
  return Array.from({ length: TAILLE_PAGE_ADMIN }, (_, i) => ({
    ...EPREUVE,
    id: i + 1,
    name: `Épreuve ${i + 1}`,
  }));
}

function session(permissions: string[]): SessionUser {
  return {
    id: 1,
    email: "admin@exemple.fr",
    display_name: "Admin",
    created_at: "2026-01-01T00:00:00Z",
    permissions,
    roles: [],
    groups: [],
  };
}

/** L'URL, telle que la page serveur la traduit en props. */
function afficher(url = "") {
  const sp = new URLSearchParams(url);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <CoursesAdminTable
        page={Number(sp.get("page"))}
        filtres={{
          id: sp.get("id") ?? undefined,
          name: sp.get("name") ?? undefined,
          event_type: sp.get("event_type") ?? undefined,
          date_from: sp.get("date_from") ?? undefined,
          date_to: sp.get("date_to") ?? undefined,
        }}
      />
    </QueryClientProvider>,
  );
}

describe("CoursesAdminTable", () => {
  beforeEach(() => {
    push.mockReset();
    listCourses.mockReset();
    countCourses.mockReset();
    countCourses.mockResolvedValue({ total: 1 });
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

  it("ouvre la page publique et la source du chronométreur", async () => {
    listCourses.mockResolvedValue([EPREUVE]);

    afficher();

    const publique = await screen.findByRole("link", { name: /page publique/i });
    expect(publique).toHaveAttribute("href", "/courses/12");

    const source = screen.getByRole("link", { name: /klikego/i });
    expect(source).toHaveAttribute("href", "https://klikego.com/nantes");
    expect(source).toHaveAttribute("target", "_blank");
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
    // Sans pagination, tout ce qui dépasse la 20ᵉ épreuve est inatteignable
    // depuis le back-office, donc ni corrigeable ni supprimable (SC-001).
    listCourses.mockResolvedValue(pleine());
    countCourses.mockResolvedValue({ total: 45 });

    afficher();
    await screen.findByText("Épreuve 1");
    await userEvent.click(screen.getByRole("button", { name: /Suivant/ }));

    expect(push).toHaveBeenCalledWith("/admin/courses?page=2");
  });

  it("lit la page et les filtres depuis l'URL", async () => {
    // C'est ce qui rend une page atteignable directement, sans la feuilleter.
    listCourses.mockResolvedValue([EPREUVE]);

    afficher("page=3&name=nantes&event_type=triathlon-m");

    await waitFor(() =>
      expect(listCourses).toHaveBeenCalledWith(
        expect.objectContaining({ page: 3, name: "nantes", event_type: "triathlon-m" }),
      ),
    );
    expect(countCourses).toHaveBeenCalledWith(
      expect.objectContaining({ name: "nantes", event_type: "triathlon-m" }),
    );
  });

  it("lit l'id depuis l'URL et le transmet aux deux requêtes", async () => {
    listCourses.mockResolvedValue([EPREUVE]);

    afficher("id=12");

    await waitFor(() =>
      expect(listCourses).toHaveBeenCalledWith(expect.objectContaining({ id: "12" })),
    );
    expect(countCourses).toHaveBeenCalledWith(expect.objectContaining({ id: "12" }));
  });

  it("filtre par identifiant d'épreuve et revient en page 1", async () => {
    listCourses.mockResolvedValue(pleine());
    countCourses.mockResolvedValue({ total: 45 });

    afficher("page=3");
    await screen.findByText("Épreuve 1");
    await userEvent.type(screen.getByPlaceholderText(/identifiant/i), "12");
    await userEvent.click(screen.getByRole("button", { name: "Filtrer" }));

    expect(push).toHaveBeenCalledWith("/admin/courses?id=12");
  });

  it("retombe en page 1 sur un « page » illisible plutôt que de rendre vide", async () => {
    listCourses.mockResolvedValue([EPREUVE]);

    afficher("page=-4");

    await waitFor(() =>
      expect(listCourses).toHaveBeenCalledWith(expect.objectContaining({ page: 1 })),
    );
  });

  it("n'offre pas de page suivante en dernière page", async () => {
    listCourses.mockResolvedValue([EPREUVE]);

    afficher();
    await screen.findByText("Triathlon de Nantes");

    expect(screen.getByRole("button", { name: /Suivant/ })).toBeDisabled();
  });

  it("annonce le nombre de pages et le total d'épreuves", async () => {
    listCourses.mockResolvedValue(pleine());
    countCourses.mockResolvedValue({ total: 130 });

    afficher();

    expect(await screen.findByText("Page 1 sur 7")).toBeInTheDocument();
    expect(screen.getByText("130 épreuves au catalogue")).toBeInTheDocument();
  });

  it("dit combien d'épreuves un filtre retient", async () => {
    listCourses.mockResolvedValue([EPREUVE]);
    countCourses.mockResolvedValue({ total: 1 });

    afficher("name=nantes");

    expect(await screen.findByText("1 épreuve correspond aux filtres")).toBeInTheDocument();
  });

  it("ne devine pas le nombre de pages tant que le total n'est pas arrivé", async () => {
    listCourses.mockResolvedValue(pleine());
    countCourses.mockReturnValue(new Promise(() => {})); // jamais résolue

    afficher();
    await screen.findByText("Épreuve 1");

    // Annoncer « sur 2 » au jugé serait pire que ne rien annoncer.
    expect(screen.getByText("Page 1")).toBeInTheDocument();
    expect(screen.queryByText(/au catalogue/)).not.toBeInTheDocument();
    // Une tranche pleine reste le signe qu'il y a une suite.
    expect(screen.getByRole("button", { name: /Suivant/ })).toBeEnabled();
  });

  it("n'offre pas de page précédente sur la première page", async () => {
    listCourses.mockResolvedValue([EPREUVE]);

    afficher();
    await screen.findByText("Triathlon de Nantes");

    expect(screen.getByRole("button", { name: /Précédent/ })).toBeDisabled();
  });

  it("filtre par nom d'épreuve et revient en page 1", async () => {
    listCourses.mockResolvedValue(pleine());
    countCourses.mockResolvedValue({ total: 45 });

    afficher("page=3");
    await screen.findByText("Épreuve 1");
    await userEvent.type(screen.getByPlaceholderText(/rechercher une épreuve/i), "vertou");
    await userEvent.click(screen.getByRole("button", { name: "Filtrer" }));

    // Rester en page 3 d'un catalogue qui vient de fondre n'afficherait rien.
    // Et `page=1` ne s'écrit pas : c'est du bruit dans une URL partagée.
    expect(push).toHaveBeenCalledWith("/admin/courses?name=vertou");
  });

  it("réinitialiser vide l'URL de ses filtres", async () => {
    listCourses.mockResolvedValue([EPREUVE]);

    afficher("name=nantes&page=2");
    await screen.findByText("Triathlon de Nantes");
    await userEvent.click(screen.getByRole("button", { name: /réinitialiser/i }));

    expect(push).toHaveBeenCalledWith("/admin/courses");
  });

  it("laisse la barre de filtres montée sur un résultat vide", async () => {
    listCourses.mockResolvedValue([]);

    afficher("name=introuvable");

    // Sans elle, l'administrateur serait enfermé dans son propre filtre.
    expect(await screen.findByText(/aucun résultat/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /réinitialiser/i })).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/rechercher une épreuve/i)).toHaveValue("introuvable");
  });
});
