import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { SessionUser } from "@/lib/types";

const { getSession, getAdminBadgeCounts, getAthlete } = vi.hoisted(() => ({ getSession: vi.fn(), getAdminBadgeCounts: vi.fn(), getAthlete: vi.fn() }));
vi.mock("@/lib/api/client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api/client")>()),
  apiClient: { getSession, getAdminBadgeCounts, getAthlete },
}));
const athlete = vi.hoisted(() => ({ current: null as null | { id: number; prenom: string; nom: string } }));
vi.mock("@/components/layout/AthletePicker", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/components/layout/AthletePicker")>()),
  useSelectedAthlete: () => athlete.current,
}));

import { currentSeason } from "@/lib/utils/season";
import { TuilesEspaces } from "./TuilesEspaces";

const BASE: SessionUser = {
  id: 1, email: "moi@exemple.fr", display_name: "Moi", created_at: "2026-01-01T00:00:00Z",
  permissions: [], roles: [], groups: [], can_administer: false, can_supervise: false, is_member: false, athlete: null, athlete_claim: null,
};

function afficher(query = "", seasons = [currentSeason()]) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <TuilesEspaces podiumsSaison={27} query={query} seasons={seasons} />
    </QueryClientProvider>,
  );
}

describe("TuilesEspaces", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    athlete.current = null;
    getAdminBadgeCounts.mockResolvedValue({});
  });

  it("links every visitor to Résultats, Club and Mon espace, with their fresh line", async () => {
    getSession.mockResolvedValue(null);
    afficher();
    expect(screen.getByRole("link", { name: /Résultats.*Toutes les épreuves du club/ })).toHaveAttribute("href", "/resultats");
    expect(screen.getByRole("link", { name: /Club.*27 podiums/ })).toHaveAttribute("href", "/club");
    expect(screen.getByRole("link", { name: /Mon espace.*Choisissez votre nom/ })).toHaveAttribute("href", "/mon-espace");
  });

  it("indexes each tile for the cascade entrance", () => {
    getSession.mockResolvedValue(null);
    const { container } = afficher();
    const entrees = [...container.querySelectorAll(".tcn-tuile-entree")];
    expect(entrees).toHaveLength(3);
    entrees.forEach((entree, i) => expect(entree.getAttribute("style")).toContain(`--i: ${i}`));
  });

  it("exposes each tile title as a level 2 heading", () => {
    getSession.mockResolvedValue(null);
    afficher();
    const titres = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
    expect(titres).toEqual(["Résultats", "Club", "Mon espace"]);
  });

  it("names the selected athlete on the Mon espace tile", () => {
    getSession.mockResolvedValue(null);
    athlete.current = { id: 7, prenom: "Léa", nom: "Écuyer" };
    getAthlete.mockReturnValue(new Promise(() => {}));
    afficher();
    expect(screen.getByRole("link", { name: "Mon espace Léa Écuyer" })).toBeInTheDocument();
  });

  it("adds the season's épreuves count once loaded", async () => {
    getSession.mockResolvedValue(null);
    athlete.current = { id: 7, prenom: "Léa", nom: "Écuyer" };
    const part = (id: number) => ({ course: { id }, is_pending_validation: false });
    getAthlete.mockResolvedValue({ participations: [part(1), part(2), part(2)] });
    afficher();
    expect(await screen.findByRole("link", { name: /Mon espace.*Léa Écuyer · 2 épreuves cette saison/ })).toBeInTheDocument();
  });

  it("shows no reserved tile without power, nor while the session is read", async () => {
    getSession.mockReturnValue(new Promise(() => {}));
    afficher();
    expect(screen.queryByRole("link", { name: /Encadrement|Back-office/ })).not.toBeInTheDocument();
  });

  it("adds Encadrement and Back-office with its « à traiter » badge for those who hold them", async () => {
    getSession.mockResolvedValue({ ...BASE, can_supervise: true, can_administer: true, permissions: ["quality:override"] });
    getAdminBadgeCounts.mockResolvedValue({ quality: 4 });
    afficher();
    expect(await screen.findByRole("link", { name: /Encadrement/ })).toHaveAttribute("href", "/encadrement");
    const backOffice = await screen.findByRole("link", { name: /Back-office/ });
    expect(backOffice).toHaveAttribute("href", "/admin");
    expect(await within(backOffice).findByText("4")).toBeInTheDocument();
    expect(backOffice).toHaveAccessibleName(/4 éléments à traiter/);
  });

  it("carries the season selection to Résultats, Club and Mon espace", () => {
    getSession.mockResolvedValue(null);
    afficher("?seasons=2025&sports=all", [2025]);
    expect(screen.getByRole("link", { name: /Résultats/ })).toHaveAttribute("href", "/resultats?seasons=2025&sports=all");
    expect(screen.getByRole("link", { name: /Club/ })).toHaveAttribute("href", "/club?seasons=2025&sports=all");
    expect(screen.getByRole("link", { name: /Mon espace/ })).toHaveAttribute("href", "/mon-espace?seasons=2025&sports=all");
  });

  it("names the single past season in the counts", () => {
    getSession.mockResolvedValue(null);
    afficher("?seasons=2024", [2024]);
    expect(screen.getByRole("link", { name: /Club.*27 podiums sur la saison 2024 — 2025/ })).toBeInTheDocument();
  });

  it("words the counts per period and requests the selected seasons", async () => {
    getSession.mockResolvedValue(null);
    athlete.current = { id: 7, prenom: "Léa", nom: "Écuyer" };
    getAthlete.mockResolvedValue({ participations: [{ course: { id: 1 }, is_pending_validation: false }] });
    afficher("?seasons=2024,2025", [2024, 2025]);
    expect(await screen.findByRole("link", { name: /Mon espace.*1 épreuve sur les 2 saisons sélectionnées/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Club.*27 podiums sur les 2 saisons sélectionnées/ })).toBeInTheDocument();
    expect(getAthlete).toHaveBeenCalledWith(7, expect.objectContaining({ seasons: "2024,2025" }));
  });

  it("draws a decorative arrow pastille in every tile without changing the link names", async () => {
    getSession.mockResolvedValue({ ...BASE, can_supervise: true, can_administer: true });
    afficher();
    await screen.findByRole("link", { name: /Back-office/ });
    const liens = screen.getAllByRole("link");
    expect(liens).toHaveLength(5);
    for (const lien of liens) {
      const fleche = lien.querySelector(".tcn-tuile-fleche");
      expect(fleche).toHaveAttribute("aria-hidden", "true");
      expect(fleche?.querySelector("svg")).not.toBeNull();
    }
    expect(liens.map((l) => l.textContent)).not.toContain("→");
    expect(screen.getByRole("link", { name: /^Résultats Toutes les épreuves du club$/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /^Encadrement Jeunes, appel, bénévolat$/ })).toBeInTheDocument();
  });
});
