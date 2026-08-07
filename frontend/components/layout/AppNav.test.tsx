import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiError } from "@/lib/api/client";
import type { SessionUser } from "@/lib/types";

const { push, getSession, logout, listParticipations, route } = vi.hoisted(() => ({
  push: vi.fn(),
  getSession: vi.fn(),
  logout: vi.fn(),
  listParticipations: vi.fn(),
  route: { pathname: "/dashboard" },
}));

/** Mutable : le surlignage se teste depuis plusieurs écrans. */
const chemin = vi.hoisted(() => ({ courant: "/dashboard" }));

vi.mock("next/navigation", () => ({
  usePathname: () => chemin.courant,
  useRouter: () => ({ push, refresh: vi.fn() }),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { listParticipations, getSession, logout } };
});

import { AppNav } from "./AppNav";
import { readAthlete } from "./AthletePicker";

function afficher(session: SessionUser | null) {
  if (session) getSession.mockResolvedValue(session);
  else getSession.mockRejectedValue(new ApiError(401, "anonyme"));

  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <AppNav />
    </QueryClientProvider>,
  );
}

const SESSION: SessionUser = {
  id: 1,
  email: "contributeur@exemple.fr",
  display_name: "contributeur",
  created_at: "2026-08-01T14:54:28Z",
  permissions: [],
  roles: [],
};

/** La même session, habilitée. `permissions` est l'unique source (#115). */
function habilite(...pouvoirs: string[]): SessionUser {
  return { ...SESSION, permissions: pouvoirs };
}

/**
 * Déplie le rail — c'est là que les libellés des entrées apparaissent.
 *
 * Idempotent : la nav **persiste** son état déplié, donc un rendu qui suit un
 * dépliage dans le même test démarre déjà ouvert.
 */
async function deplier() {
  const bouton = screen.queryByRole("button", { name: "Déplier la navigation" });
  if (bouton) await userEvent.click(bouton);
}

beforeEach(() => {
  push.mockClear();
  chemin.courant = "/dashboard";
  listParticipations.mockResolvedValue([]);

  // Node 20 (la CI) fournit `window.localStorage` à jsdom, Node 26 non. Sans
  // stock déterministe, la persistance de l'état déplié fuit d'un test à
  // l'autre sur l'un des deux et pas sur l'autre.
  const stock = new Map<string, string>();
  Object.defineProperty(window, "localStorage", {
    configurable: true,
    value: {
      getItem: (cle: string) => stock.get(cle) ?? null,
      setItem: (cle: string, valeur: string) => void stock.set(cle, valeur),
      removeItem: (cle: string) => void stock.delete(cle),
      clear: () => stock.clear(),
    },
  });
});

describe("readAthlete — stock corrompu", () => {
  it("traite une valeur illisible ou de mauvaise forme comme une absence de choix", () => {
    // Le stock est éditable : sans garde, `{ id: "1" }` passerait le
    // `JSON.parse` puis planterait à l'affichage (`name.split`).
    window.localStorage.setItem("tcn-athlete", JSON.stringify({ id: "1" }));
    expect(readAthlete()).toBeNull();

    window.localStorage.setItem("tcn-athlete", "pas du json");
    expect(readAthlete()).toBeNull();

    window.localStorage.setItem("tcn-athlete", JSON.stringify({ id: 7, name: "Marie Gaudin" }));
    expect(readAthlete()).toEqual({ id: 7, name: "Marie Gaudin" });
  });
});

describe("AppNav — actions primaires", () => {
  it("ancre « Ajouter une course » et « Rechercher un athlète », même replié", async () => {
    afficher(null);
    // Repliée, la nav n'a plus de libellé visible : ce sont les noms
    // accessibles qui portent l'action.
    expect(screen.getAllByRole("link", { name: "Ajouter une course" }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("button", { name: "Rechercher un athlète" }).length).toBeGreaterThan(0);
  });

  it("ouvre le picker au ⌘K / Ctrl+K depuis n'importe où", async () => {
    afficher(null);
    await userEvent.keyboard("{Control>}k{/Control}");

    const modale = await screen.findByRole("dialog");
    expect(within(modale).getByText("Sélectionne ton nom")).toBeInTheDocument();
    expect(within(modale).getByText("Saisis au moins 2 lettres de ton nom.")).toBeInTheDocument();
  });
});

describe("AppNav — arborescence", () => {
  it("mène aux écrans livrés et porte les autres désactivés", async () => {
    afficher(null);
    await deplier();

    expect(screen.getByRole("link", { name: "Tableau de bord" })).toHaveAttribute("href", "/dashboard");
    expect(screen.getByRole("link", { name: "Résultats" })).toHaveAttribute("href", "/resultats");

    // Sans écran livré : l'entrée est portée, annoncée « À VENIR », mais
    // n'est pas un lien.
    expect(screen.queryByRole("link", { name: "Carte" })).not.toBeInTheDocument();
    expect(screen.getByText("Carte")).toBeInTheDocument();
    expect(screen.getAllByText("À VENIR").length).toBeGreaterThan(0);
  });

  it("marque l'entrée courante avec aria-current=\"page\"", async () => {
    afficher(null);
    await deplier();
    expect(screen.getByRole("link", { name: "Tableau de bord" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Résultats" })).not.toHaveAttribute("aria-current");
  });

  it("cache Administration à un anonyme et la montre à un connecté", async () => {
    const { unmount } = afficher(null);
    await deplier();
    expect(screen.queryByText("Administration")).not.toBeInTheDocument();
    unmount();

    afficher(SESSION);
    await deplier();
    await waitFor(() => expect(screen.getByText("Administration")).toBeInTheDocument());
    expect(screen.getByRole("link", { name: "Fournisseurs en attente" })).toHaveAttribute(
      "href",
      "/admin/fournisseurs",
    );
    expect(screen.getByRole("link", { name: "Gestion des courses" })).toHaveAttribute(
      "href",
      "/admin/courses",
    );
    // Les entrées d'échelon administrateur attendent #115 : rien ne l'attribue.
    expect(screen.queryByText("Feature flags")).not.toBeInTheDocument();
  });

  it("n'allume qu'une entrée d'administration à la fois", async () => {
    chemin.courant = "/admin/courses";
    afficher(SESSION);
    await deplier();

    // `isActive` teste `startsWith` : une entrée branchée sur `/admin` serait
    // allumée sur **tous** les écrans d'administration.
    await waitFor(() =>
      expect(screen.getByRole("link", { name: "Gestion des courses" })).toHaveAttribute(
        "aria-current",
        "page",
      ),
    );
    expect(
      screen.getByRole("link", { name: "Fournisseurs en attente" }),
    ).not.toHaveAttribute("aria-current");
  });
});

describe("AppNav — Gestion des utilisateurs (#170)", () => {
  /**
   * La section se règle sur les **pouvoirs**, pas sur `ROLE.ADMIN`.
   *
   * `rank` ne vaut jamais `ROLE.ADMIN` (rien ne le calcule) : une entrée à cet
   * échelon est invisible pour tout le monde, ce qui rendrait l'écran des accès
   * inatteignable depuis la nav. `session.permissions` est, lui, renseigné par
   * `/auth/me` depuis #115.
   *
   * Ce filtre est un confort d'affichage, jamais une garde : l'API refuse
   * elle-même sans `allowed_emails:manage`.
   */
  it("cache la section à un connecté sans pouvoir", async () => {
    afficher(SESSION);
    await deplier();
    await waitFor(() => expect(screen.getByText("Administration")).toBeInTheDocument());
    expect(screen.queryByText("Gestion des utilisateurs")).not.toBeInTheDocument();
  });

  it("ouvre « Accès au back-office » à qui porte allowed_emails:manage", async () => {
    afficher(habilite("allowed_emails:manage"));
    await deplier();
    await waitFor(() => expect(screen.getByText("Gestion des utilisateurs")).toBeInTheDocument());
    expect(screen.getByRole("link", { name: "Accès au back-office" })).toHaveAttribute(
      "href",
      "/admin/acces",
    );
  });

  it("ne surligne que la destination courante, jamais son préfixe", async () => {
    // `startsWith` allumait « Chronométreurs signalés » (href `/admin`) en même
    // temps que l'écran des accès. Un href de la nav désigne **un** écran, pas
    // une famille : les trois écrans à venir vivront eux aussi sous `/admin/`.
    chemin.courant = "/admin/acces";
    afficher(habilite("allowed_emails:manage"));
    await deplier();

    const courant = await screen.findByRole("link", { name: "Accès au back-office" });
    expect(courant).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Chronométreurs signalés" })).not.toHaveAttribute(
      "aria-current",
    );
  });

  it("ne porte que les entrées dont le pouvoir est détenu", async () => {
    // Composer les droits d'un rôle et autoriser une adresse sont deux pouvoirs
    // distincts : porter l'un ne doit pas annoncer l'écran de l'autre.
    afficher(habilite("roles:write"));
    await deplier();
    await waitFor(() => expect(screen.getByText("Gestion des utilisateurs")).toBeInTheDocument());

    expect(screen.getByText("Droits des rôles")).toBeInTheDocument();
    expect(screen.queryByText("Accès au back-office")).not.toBeInTheDocument();
    expect(screen.queryByText("Groupes d'appartenance")).not.toBeInTheDocument();
  });

  it("porte les écrans non livrés désactivés plutôt que de les inventer", async () => {
    afficher(habilite("roles:assign", "groups:assign"));
    await deplier();
    await waitFor(() => expect(screen.getByText("Gestion des utilisateurs")).toBeInTheDocument());

    for (const libelle of ["Rôles des utilisateurs", "Groupes d'appartenance"]) {
      expect(screen.getByText(libelle)).toBeInTheDocument();
      expect(screen.queryByRole("link", { name: libelle })).not.toBeInTheDocument();
    }
  });
});

describe("AppNav — session (#114)", () => {
  it("propose « Se connecter » à un visiteur anonyme, par le routeur", async () => {
    afficher(null);
    const [bouton] = await screen.findAllByRole("button", { name: "Se connecter" });

    // Un `<a>` enveloppant un `<button>` est un HTML invalide, annoncé deux
    // fois par les technologies d'assistance.
    expect(bouton.closest("a")).toBeNull();

    await userEvent.click(bouton);
    expect(push).toHaveBeenCalledWith("/login");
  });

  it("regroupe l'état connecté derrière un déclencheur unique (#176)", async () => {
    afficher(SESSION);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: `Compte — ${SESSION.email}` })).toBeInTheDocument(),
    );
    expect(screen.queryByRole("button", { name: "Se déconnecter" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Se connecter" })).not.toBeInTheDocument();
  });

  it("pose l'action dans le tiroir mobile aussi, sans dupliquer l'entrée Administration", async () => {
    // Le tiroir déplie l'état connecté **à plat** : un menu déroulant y
    // sortirait du piège de focus. Le lien « Administration » a été **retiré**
    // du menu compte (revue humaine PR #214) : la catégorie Administration de
    // la nav rend l'entrée redondante.
    afficher(SESSION);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: `Compte — ${SESSION.email}` })).toBeInTheDocument(),
    );

    await userEvent.click(screen.getByRole("button", { name: "Ouvrir le menu" }));

    const tiroir = await screen.findByRole("dialog");
    expect(within(tiroir).getByText(SESSION.email)).toBeInTheDocument();
    // Le tiroir de compte ne doit plus porter d'entrée « Administration » :
    // seule la nav la porte désormais. `within(tiroir)` isole la portée : la
    // catégorie « Administration » de la nav vit hors du tiroir.
    expect(within(tiroir).queryByRole("link", { name: "Administration" })).not.toBeInTheDocument();
    expect(within(tiroir).getByRole("button", { name: "Se déconnecter" })).toBeInTheDocument();
  });
});
