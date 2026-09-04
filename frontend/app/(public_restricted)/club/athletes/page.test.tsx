import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { currentSeason } from "@/lib/utils/season";

const listAthleteSeasonActivity = vi.fn();
const listSeasons = vi.fn();
const getSession = vi.fn();

vi.mock("@/lib/api/server", () => ({
  apiServer: {
    listAthleteSeasonActivity: (opts: unknown) => listAthleteSeasonActivity(opts),
    listSeasons: (opts: unknown) => listSeasons(opts),
    getSession: () => getSession(),
  },
}));

// SeasonSelector est un composant client : `usePathname`/`useSearchParams`
// doivent être mockés pour que le rendu de la page (RSC) ne plante pas. La
// query string est mutable : la ligne de tags ne se rend qu'à deux saisons.
const url = vi.hoisted(() => ({ qs: "" }));

// `vi.hoisted` : le shorthand `{ redirect }` du mock ci-dessous évalue la
// variable au moment où la factory s'exécute, pas à l'appel — un simple
// `const` plus bas serait encore non initialisé (patron d'`app/admin/layout.test.tsx`).
const { redirect } = vi.hoisted(() => ({
  redirect: vi.fn(() => {
    // `redirect()` de Next interrompt le rendu en levant : le simuler à
    // l'identique est ce qui prouve que rien n'est rendu après la garde.
    throw new Error("NEXT_REDIRECT");
  }),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => "/club/athletes",
  useSearchParams: () => new URLSearchParams(url.qs),
  redirect,
}));

import AthletesSeasonPage from "./page";

const SESSION_AVEC_POUVOIR = {
  id: 1,
  email: "contributeur@exemple.fr",
  display_name: "contributeur",
  created_at: "2026-08-01T14:54:28Z",
  permissions: ["pages:preview"],
  roles: [],
};

beforeEach(() => {
  vi.clearAllMocks();
  url.qs = "";
  getSession.mockResolvedValue(SESSION_AVEC_POUVOIR);
  listAthleteSeasonActivity.mockReset().mockResolvedValue([
    { id: 1, nom: "DUPONT", prenom: "Jean", participation_count: 2 },
  ]);
  listSeasons.mockReset().mockResolvedValue([
    { start_year: currentSeason(), label: "Saison en cours", event_count: 1, participation_count: 2, is_current: true },
  ]);
});

async function renderPage(searchParams: Record<string, string | undefined> = {}) {
  const ui = await AthletesSeasonPage({ searchParams: Promise.resolve(searchParams) });
  return render(ui);
}

describe("/club/athletes", () => {
  it("appelle l'API scopée club, saison en cours par défaut", async () => {
    await renderPage();

    expect(listAthleteSeasonActivity).toHaveBeenCalledWith(
      expect.objectContaining({ scope: "club", seasons: [currentSeason()] }),
    );
  });

  it("rend la liste des athlètes actifs renvoyée par l'API", async () => {
    await renderPage();

    expect(screen.getByText("DUPONT")).toBeInTheDocument();
  });

  it("lit ?seasons= dans l'URL et l'utilise à la place de la saison en cours (US2)", async () => {
    await renderPage({ seasons: "2023" });

    expect(listAthleteSeasonActivity).toHaveBeenCalledWith(
      expect.objectContaining({ scope: "club", seasons: [2023] }),
    );
  });

  it("rend le sélecteur de saison, alimenté par apiServer.listSeasons", async () => {
    await renderPage();

    expect(listSeasons).toHaveBeenCalledWith(expect.objectContaining({ scope: "club" }));
    expect(screen.getByLabelText("Choisir les saisons")).toBeInTheDocument();
  });

  it("filtre aux disciplines fédérales par défaut, comme /dashboard et /club (#382)", async () => {
    await renderPage();

    expect(listAthleteSeasonActivity).toHaveBeenCalledWith(
      expect.objectContaining({ federal_only: true }),
    );
  });

  it("lit ?sports=all pour inclure les autres disciplines (#382)", async () => {
    await renderPage({ sports: "all" });

    expect(listAthleteSeasonActivity).toHaveBeenCalledWith(
      expect.objectContaining({ federal_only: undefined }),
    );
  });

  it("rend le DisciplineToggle (#382)", async () => {
    await renderPage();

    expect(screen.getByText("Inclure les autres disciplines")).toBeInTheDocument();
  });

  it("rattache la ligne de tags à l'en-tête, pas à la liste (revue UI/UX)", async () => {
    // Posée en enfant du `space-y-8`, la ligne se retrouvait à 32 px de
    // l'en-tête **et** 32 px de la liste : rien ne disait à quoi elle
    // appartenait. Groupée avec l'en-tête, sa distance au titre est plus
    // courte que sa distance à la liste.
    url.qs = "seasons=2023,2024";
    await renderPage({ seasons: "2023,2024" });

    const tags = screen.getByTestId("season-tags");
    const groupe = tags.parentElement;

    expect(groupe).not.toBeNull();
    expect(groupe).toContainElement(screen.getByRole("heading", { name: "Athlètes par saison" }));
    expect(groupe).not.toContainElement(screen.getByText("DUPONT"));
  });

  it("aligne les tags comme le slot d'actions, qui bascule au palier sm (revue UI/UX)", async () => {
    url.qs = "seasons=2023,2024";
    await renderPage({ seasons: "2023,2024" });

    expect(screen.getByTestId("season-tags")).toHaveClass("justify-start", "sm:justify-end");
  });

  // #487 : les deux écrans club se relient dans les deux sens. /club renvoie
  // ici par « Voir les N athlètes → » ; le retour manquait.
  it("renvoie vers /club", async () => {
    await renderPage();

    expect(screen.getByRole("link", { name: /Espace club/ })).toHaveAttribute("href", "/club");
  });

  // #811 — la garde côté écran, jumelle de celle posée sur l'API.
  // #831 — un message explicite en place, plus jamais un renvoi silencieux.
  describe("garde pages:preview (#811, #831)", () => {
    it("affiche un message explicite pour un anonyme, sans rediriger", async () => {
      getSession.mockResolvedValue(null);

      await renderPage();

      expect(redirect).not.toHaveBeenCalled();
      expect(listAthleteSeasonActivity).not.toHaveBeenCalled();
      expect(listSeasons).not.toHaveBeenCalled();
      expect(screen.getByText(/Vous n'avez pas la permission nécessaire/)).toBeInTheDocument();
      expect(screen.getByText(/Voir les pages en avant-première/)).toBeInTheDocument();
    });

    it("affiche un message explicite pour un connecté sans le pouvoir, sans rediriger", async () => {
      getSession.mockResolvedValue({ ...SESSION_AVEC_POUVOIR, permissions: [] });

      await renderPage();

      expect(redirect).not.toHaveBeenCalled();
      expect(listAthleteSeasonActivity).not.toHaveBeenCalled();
      expect(listSeasons).not.toHaveBeenCalled();
      expect(screen.getByText(/Vous n'avez pas la permission nécessaire/)).toBeInTheDocument();
    });

    it("garde le lien de retour vers /club sur l'écran de refus", async () => {
      getSession.mockResolvedValue({ ...SESSION_AVEC_POUVOIR, permissions: [] });

      await renderPage();

      expect(screen.getByRole("link", { name: /Espace club/ })).toHaveAttribute("href", "/club");
    });

    it("rend la page pour qui détient pages:preview", async () => {
      await renderPage();

      expect(redirect).not.toHaveBeenCalled();
      expect(screen.getByText("DUPONT")).toBeInTheDocument();
    });
  });
});
