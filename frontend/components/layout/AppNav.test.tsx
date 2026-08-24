import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiError } from "@/lib/api/client";
import type { SessionUser } from "@/lib/types";

const { push, getSession, logout, listParticipations, countCourses } = vi.hoisted(() => ({
  push: vi.fn(),
  getSession: vi.fn(),
  logout: vi.fn(),
  listParticipations: vi.fn(),
  countCourses: vi.fn(),
}));

/** Mutable : le surlignage se teste depuis plusieurs écrans. */
const chemin = vi.hoisted(() => ({ courant: "/dashboard" }));

/**
 * Montages de `next/link` par route, `prefetch={false}` exclu (#428).
 *
 * C'est le seul proxy fidèle du prefetch : Next.js le déclenche à l'entrée du
 * nœud dans le viewport, donc **une fois par montage**. Un `Link` démonté puis
 * remonté pour la même route retire son `IntersectionObserver` et en pose un
 * neuf, d'où un second prefetch — invisible dans le DOM, mais compté ici.
 */
const montages = vi.hoisted(() => new Map<string, number>());

vi.mock("next/navigation", () => ({
  usePathname: () => chemin.courant,
  useRouter: () => ({ push, refresh: vi.fn() }),
}));

// `prefetch` ne se reflète sur aucun attribut DOM du <a> réel de next/link
// (comportement purement interne, piloté par IntersectionObserver) : on ne
// peut donc vérifier son câblage qu'en interceptant le composant lui-même.
vi.mock("next/link", async () => {
  const { useEffect } = await import("react");
  function Lien({
    href,
    prefetch,
    children,
    ...rest
  }: {
    href: string;
    prefetch?: boolean;
    children?: ReactNode;
    [key: string]: unknown;
  }) {
    useEffect(() => {
      if (prefetch === false) return;
      montages.set(href, (montages.get(href) ?? 0) + 1);
    }, [href, prefetch]);
    return (
      <a href={href} data-prefetch={String(prefetch)} {...rest}>
        {children}
      </a>
    );
  }
  return { default: Lien };
});

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { listParticipations, getSession, logout, countCourses } };
});

import { AppNav } from "./AppNav";
import { clearAthlete, readAthlete, writeAthlete } from "./AthletePicker";

function afficher(session: SessionUser | null, { initialExpanded = false }: { initialExpanded?: boolean } = {}) {
  if (session) getSession.mockResolvedValue(session);
  else getSession.mockRejectedValue(new ApiError(401, "anonyme"));

  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <AppNav initialExpanded={initialExpanded} />
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
  groups: [],
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
  montages.clear();
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

  // Le cookie de largeur (#482, NAV-3) n'est réinitialisé par aucun mock —
  // contrairement à `localStorage` ci-dessus, `document.cookie` est un vrai
  // objet du document jsdom qui persiste d'un test à l'autre dans le même fichier.
  document.cookie = "tcn-nav-expanded=; path=/; max-age=0";
});

describe("readAthlete — stock corrompu", () => {
  it("traite une valeur illisible ou de mauvaise forme comme une absence de choix", () => {
    // Le stock est éditable : sans garde, `{ id: "1" }` passerait le
    // `JSON.parse` puis planterait à l'affichage.
    window.localStorage.setItem("tcn-athlete", JSON.stringify({ id: "1" }));
    expect(readAthlete()).toBeNull();

    window.localStorage.setItem("tcn-athlete", "pas du json");
    expect(readAthlete()).toBeNull();

    window.localStorage.setItem("tcn-athlete", JSON.stringify({ id: 7, prenom: "Marie", nom: "Gaudin" }));
    expect(readAthlete()).toEqual({ id: 7, prenom: "Marie", nom: "Gaudin" });
  });

  it("refuse un stock qui ne porte que le nom complet (#264)", () => {
    // Forme abandonnée : `{ id, name }` obligeait le rail à redécouper le
    // prénom, ce qu'aucune heuristique ne fait juste. Un stock d'avant le
    // correctif est une absence de choix — l'athlète se re-sélectionne une fois.
    window.localStorage.setItem("tcn-athlete", JSON.stringify({ id: 7, name: "Marie Gaudin" }));
    expect(readAthlete()).toBeNull();
  });
});

describe("AppNav — prefetch de la tuile « Mon profil » (#425)", () => {
  it("désactive le prefetch des deux liens vers /athletes/{id} — un athlète épinglé au hasard, pas une destination probable", async () => {
    window.localStorage.setItem("tcn-athlete", JSON.stringify({ id: 12, prenom: "Jean", nom: "Dupont" }));
    afficher(null);
    await deplier();

    expect(screen.getByRole("link", { name: "Mon profil — Jean Dupont" })).toHaveAttribute(
      "data-prefetch",
      "false",
    );
    expect(await screen.findByRole("link", { name: "Jean" })).toHaveAttribute("data-prefetch", "false");
  });
});

describe("AppNav — doublon de prefetch après resynchro localStorage (#428)", () => {
  /**
   * Le rendu serveur part du rail replié ; l'effet de montage lit
   * `localStorage` et déplie. Tant que les deux états rendaient deux blocs JSX
   * mutuellement exclusifs (`Tuile` ↔ `Entree`), cette bascule démontait les
   * `Link` du rail pour en monter d'autres vers les **mêmes** routes, déjà dans
   * le viewport : second prefetch RSC pour rien (sondage
   * `2026-08-17-dashboard-perf-rank-et-prefetch-sondage.md`, constat 2).
   */
  it("ne prefetche « Résultats » qu'une fois quand le rail persisté est déjà déplié", async () => {
    afficher(null, { initialExpanded: true });

    // Le rail est déjà déplié dès le premier rendu — synchrone, sans attendre
    // un effet de montage (#482, NAV-3) : c'est exactement ce que ce correctif
    // change par rapport à l'ancien comportement, qui exigeait un `findByRole`.
    // Scopé au rail : Task 6 y ajoute une barre basse mobile qui porte, elle
    // aussi, une entrée « Résultats ».
    const rail = screen.getByRole("navigation", { name: "Navigation principale" });
    expect(within(rail).getByRole("link", { name: "Résultats" })).toBeInTheDocument();
    // 2, pas 1 : la barre basse mobile (#482, NAV-4) monte son propre `Link`
    // vers la même route, en plus de celui du rail — même limite assumée que
    // le logo/bouton d'ajout du pied mobile (frontend/AGENTS.md, « #428 »).
    expect(montages.get("/resultats")).toBe(2);
  });

  it("garde l'entrée montée d'un pliage et d'un dépliage à la main", async () => {
    // Le cookie côté serveur n'aurait évité que la bascule de l'atterrissage.
    // Le bouton de dépliage, lui, la rejoue à chaque clic.
    afficher(null);
    await userEvent.click(screen.getByRole("button", { name: "Déplier la navigation" }));
    await userEvent.click(screen.getByRole("button", { name: "Replier la navigation" }));

    // 2 : le rail (une seule fois, l'objet de ce test) + la barre basse
    // mobile, toujours montée (#482, NAV-4).
    expect(montages.get("/resultats")).toBe(2);
  });

  it("remonte l'entrée d'une catégorie à plusieurs destinations à chaque dépliage — limite assumée du correctif", async () => {
    // Caractérisation, pas un objectif : l'unification ne vaut que pour la
    // section **racine** et, depuis #482 (NAV-2), pour une catégorie réduite à
    // une seule destination livrée (« Club », qui rend désormais son `Link`
    // dans les deux états et échappe donc à cette limite). Une catégorie à
    // *plusieurs* destinations livrées (« Administration ») repliée n'offre
    // toujours qu'une tuile qui déplie : ses `Link` n'existent pas, donc il
    // n'y a rien à réutiliser à la bascule.
    // Sans conséquence à l'atterrissage — ils ne montent qu'une fois — et le
    // bouton de catégorie est resté hors périmètre de #428.
    afficher(habilite("pending_providers:read", "batch:run"));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Administration" })).toBeInTheDocument(),
    );

    await userEvent.click(screen.getByRole("button", { name: "Déplier la navigation" }));
    expect(montages.get("/admin/fournisseurs")).toBe(1);

    await userEvent.click(screen.getByRole("button", { name: "Replier la navigation" }));
    await userEvent.click(screen.getByRole("button", { name: "Déplier la navigation" }));
    expect(montages.get("/admin/fournisseurs")).toBe(2);
    // La racine, elle, tient : c'est ce que le correctif garantit. 2, pas 1 :
    // la barre basse mobile (#482, NAV-4) porte, elle aussi, « Résultats ».
    expect(montages.get("/resultats")).toBe(2);
  });

  it("ne prefetche pas le logo du rail déplié, qui double la route de « Tableau de bord »", async () => {
    afficher(null, { initialExpanded: true });

    const rail = screen.getByRole("navigation", { name: "Navigation principale" });
    const logo = within(rail).getByRole("link", { name: "TCN — Accueil" });
    expect(logo).toHaveAttribute("href", "/dashboard");
    expect(logo).toHaveAttribute("data-prefetch", "false");
  });
});

describe("AppNav — largeur du rail décidée avant la peinture (#482, NAV-3)", () => {
  it("réplique replié par défaut quand aucune prop n'est fournie", () => {
    afficher(null);

    const rail = screen.getByRole("navigation", { name: "Navigation principale" });
    expect(rail.style.width).toBe("var(--tcn-nav-rail)");
  });

  it("peint le rail à sa largeur persistée dès le premier rendu, sans jamais lire localStorage", () => {
    // Le stock localStorage reste vide : si le rail lisait encore
    // `tcn-nav-expanded` depuis là, la prop n'aurait aucun effet.
    afficher(null, { initialExpanded: true });

    const rail = screen.getByRole("navigation", { name: "Navigation principale" });
    expect(rail.style.width).toBe("var(--tcn-nav-panel)");
    expect(window.localStorage.getItem("tcn-nav-expanded")).toBeNull();
  });

  it("écrit un cookie — jamais localStorage — quand on (re)plie le rail à la main", async () => {
    afficher(null);
    await userEvent.click(screen.getByRole("button", { name: "Déplier la navigation" }));

    expect(document.cookie).toContain("tcn-nav-expanded=1");
    expect(window.localStorage.getItem("tcn-nav-expanded")).toBeNull();

    await userEvent.click(screen.getByRole("button", { name: "Replier la navigation" }));
    expect(document.cookie).toContain("tcn-nav-expanded=0");
  });
});

describe("AppNav — monogramme du rail replié (#482, NAV-2)", () => {
  it("porte un lien vers /dashboard même rail replié, alors qu'aucune marque n'existait avant", () => {
    afficher(null);

    const rail = screen.getByRole("navigation", { name: "Navigation principale" });
    const monogramme = within(rail).getByRole("link", { name: "TCN — Accueil" });
    expect(monogramme).toHaveAttribute("href", "/dashboard");
    expect(monogramme).toHaveTextContent("TCN");
  });

  it("ne double pas le monogramme une fois le rail déplié — seul le logo image reste", () => {
    afficher(null, { initialExpanded: true });

    const rail = screen.getByRole("navigation", { name: "Navigation principale" });
    expect(within(rail).getAllByRole("link", { name: "TCN — Accueil" })).toHaveLength(1);
  });
});

describe("AppNav — prénom de l'athlète retenu (#264)", () => {
  /**
   * Un prénom composé sans trait d'union — « Jean Gael » — est **un** prénom.
   * Le rail affichait `name.split(" ")[0]`, donc « Jean », alors que
   * « Jean-Gaël » passait entier : la troncature ne dépendait que de la
   * présence d'une espace. Le prénom vient désormais du champ `prenom` de
   * l'API, jamais d'un découpage du nom complet.
   */
  it("affiche un prénom composé en entier", async () => {
    window.localStorage.setItem(
      "tcn-athlete",
      JSON.stringify({ id: 12, prenom: "Jean Gael", nom: "Dupont" }),
    );
    afficher(null);
    await deplier();

    expect(await screen.findByRole("link", { name: "Jean Gael" })).toHaveAttribute(
      "href",
      "/athletes/12",
    );
    expect(screen.queryByRole("link", { name: "Jean" })).not.toBeInTheDocument();
    // Le nom complet reste porté par le profil et l'avatar, pas par le libellé.
    expect(screen.getByRole("link", { name: "Mon profil — Jean Gael Dupont" })).toBeInTheDocument();
  });

  it("retient le prénom tel que l'API le donne, sans le reconstruire (#264)", async () => {
    // Le bout en bout : le picker écrit le stock que le rail relit. C'est
    // `AthletePicker` qui aplatissait `prenom` et `nom` en une seule chaîne,
    // rendant le prénom indevinable en aval.
    listParticipations.mockResolvedValue([
      { athlete: { id: 12, prenom: "Jean Gael", nom: "Dupont", gender: "M", club: "TCN" } },
    ]);
    afficher(null);
    await userEvent.keyboard("{Control>}k{/Control}");

    const modale = await screen.findByRole("dialog");
    await userEvent.type(within(modale).getByPlaceholderText("Rechercher un nom…"), "dupont");
    await userEvent.click(await screen.findByRole("button", { name: "Choisir Jean Gael Dupont" }));

    expect(readAthlete()).toEqual({ id: 12, prenom: "Jean Gael", nom: "Dupont" });
    expect(push).toHaveBeenCalledWith("/athletes/12");
  });
});

describe("AppNav — ne plus suivre l'athlète retenu (#442)", () => {
  const JEAN = { id: 12, prenom: "Jean", nom: "Dupont" };

  it("retire l'athlète du rail et du stock d'un clic sur la croix de la tuile", async () => {
    // Jusqu'ici, la désélection n'existait que sur la page de l'athlète
    // (`SelectAthleteButton`) : depuis la nav, on ne pouvait que remplacer
    // l'athlète retenu par un autre, jamais n'en retenir aucun.
    window.localStorage.setItem("tcn-athlete", JSON.stringify(JEAN));
    afficher(null);
    await deplier();

    await userEvent.click(await screen.findByRole("button", { name: "Ne plus choisir Jean Dupont" }));

    expect(readAthlete()).toBeNull();
    expect(screen.queryByRole("link", { name: "Mon profil — Jean Dupont" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Ne plus choisir Jean Dupont" })).not.toBeInTheDocument();
  });

  it("dit « ne plus choisir », le verbe déjà arbitré ailleurs (revue UI/UX)", async () => {
    // `SelectAthleteButton` rend « Ne plus choisir cet athlète » et
    // `AthletePicker` « Choisir <nom> » — vocabulaire harmonisé après la revue
    // de #323. « Suivre » y ajoutait un troisième verbe pour le même geste, et
    // promettait un abonnement qui n'existe pas.
    window.localStorage.setItem("tcn-athlete", JSON.stringify(JEAN));
    afficher(null);
    await deplier();

    const croix = await screen.findByRole("button", { name: "Ne plus choisir Jean Dupont" });
    expect(croix).toHaveAttribute("title", "Ne plus choisir");
    expect(screen.queryByRole("button", { name: /suivre/i })).not.toBeInTheDocument();
  });

  it("porte .tcn-icon-btn, seule à exprimer :hover et :focus-visible (revue UI/UX)", async () => {
    // Stylée en ligne, la croix n'avait ni survol ni anneau de focus : il ne
    // restait que l'anneau UA `outline-ring/50`, mesuré à 1,85:1 sur le fond
    // de la tuile, sous le seuil WCAG 1.4.11 de 3:1. Même cause commune que
    // les trois défauts de #299 — un `style` en ligne ne peut pas exprimer
    // d'état.
    window.localStorage.setItem("tcn-athlete", JSON.stringify(JEAN));
    afficher(null);
    await deplier();

    expect(await screen.findByRole("button", { name: "Ne plus choisir Jean Dupont" })).toHaveClass(
      "tcn-icon-btn",
    );
  });

  it("offre une cible de 44 px, la tuile en faisant déjà autant (revue UI/UX)", async () => {
    // 28 px tenait WCAG 2.5.8 (24 px) mais pas le plancher tactile de cette
    // grille, et la croix **est** rendue dans le tiroir mobile
    // (`contenu(true, …)`). La hauteur ne coûte rien : la tuile fait 44 px.
    window.localStorage.setItem("tcn-athlete", JSON.stringify(JEAN));
    afficher(null);
    await deplier();

    const croix = await screen.findByRole("button", { name: "Ne plus choisir Jean Dupont" });
    expect(croix.style.width).toBe("44px");
    expect(croix.style.height).toBe("44px");
  });

  it("laisse l'entrée « Rechercher un athlète » en place après la désélection", async () => {
    // La tuile s'affiche en complément de la recherche, jamais à sa place
    // (#323) : la retirer ne doit pas emporter le seul moyen d'en choisir un
    // autre.
    window.localStorage.setItem("tcn-athlete", JSON.stringify(JEAN));
    afficher(null);
    await deplier();
    await userEvent.click(await screen.findByRole("button", { name: "Ne plus choisir Jean Dupont" }));

    expect(screen.getAllByRole("button", { name: "Rechercher un athlète" }).length).toBeGreaterThan(0);
  });

  it("n'offre pas la croix sur le rail replié, où la tuile se réduit à l'avatar", async () => {
    // 44 px de large, l'avatar occupe la tuile entière : une croix y serait
    // à l'étroit et sans libellé lisible. Le rail se déplie d'un clic.
    window.localStorage.setItem("tcn-athlete", JSON.stringify(JEAN));
    afficher(null);

    expect(await screen.findByRole("link", { name: "Mon profil — Jean Dupont" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Ne plus choisir/ })).not.toBeInTheDocument();
  });
});

describe("AppNav — actions primaires", () => {
  it("ancre « Ajouter une épreuve » et « Rechercher un athlète », même replié", async () => {
    afficher(null);
    // Repliée, la nav n'a plus de libellé visible : ce sont les noms
    // accessibles qui portent l'action.
    expect(screen.getAllByRole("link", { name: "Ajouter une épreuve" }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("button", { name: "Rechercher un athlète" }).length).toBeGreaterThan(0);
  });

  it("ouvre le picker au ⌘K / Ctrl+K depuis n'importe où", async () => {
    afficher(null);
    await userEvent.keyboard("{Control>}k{/Control}");

    const modale = await screen.findByRole("dialog");
    expect(within(modale).getByText("Sélectionnez votre nom")).toBeInTheDocument();
    expect(within(modale).getByText("Saisissez au moins 2 lettres de votre nom.")).toBeInTheDocument();
  });

  it("garde la recherche accessible en plus de la tuile, athlète retenu, rail déplié (#323)", async () => {
    window.localStorage.setItem("tcn-athlete", JSON.stringify({ id: 12, prenom: "Jean", nom: "Dupont" }));
    afficher(null);
    await deplier();

    // Scopé au rail : la barre mobile porte toujours son propre bouton
    // loupe, indépendant de l'état de sélection, et ne doit pas fausser
    // l'assertion sur le rail lui-même.
    const rail = screen.getByRole("navigation", { name: "Navigation principale" });
    expect(within(rail).getByRole("button", { name: "Rechercher un athlète" })).toBeInTheDocument();
    expect(within(rail).getByRole("link", { name: "Mon profil — Jean Dupont" })).toBeInTheDocument();
  });

  it("garde une icône de recherche cliquable, athlète retenu, rail replié (#323)", async () => {
    // Le cas bloquant de l'issue #323 : seul le raccourci clavier ouvrait la
    // recherche une fois un athlète retenu et le rail replié — aucune icône
    // n'était rendue.
    window.localStorage.setItem("tcn-athlete", JSON.stringify({ id: 12, prenom: "Jean", nom: "Dupont" }));
    afficher(null);
    const rail = screen.getByRole("navigation", { name: "Navigation principale" });
    await userEvent.click(within(rail).getByRole("button", { name: "Rechercher un athlète" }));

    expect(await screen.findByRole("dialog")).toBeInTheDocument();
  });

  it("ouvre le picker au clavier même avec un athlète retenu", async () => {
    window.localStorage.setItem("tcn-athlete", JSON.stringify({ id: 12, prenom: "Jean", nom: "Dupont" }));
    afficher(null);
    await userEvent.keyboard("{Control>}k{/Control}");

    expect(await screen.findByRole("dialog")).toBeInTheDocument();
  });

  it("affiche aussi la recherche et la tuile dans le tiroir mobile, athlète retenu", async () => {
    window.localStorage.setItem("tcn-athlete", JSON.stringify({ id: 12, prenom: "Jean", nom: "Dupont" }));
    afficher(null);
    await userEvent.click(screen.getByRole("button", { name: "Ouvrir le menu" }));

    const tiroir = await screen.findByRole("dialog");
    expect(within(tiroir).getByRole("button", { name: "Rechercher un athlète" })).toBeInTheDocument();
    expect(within(tiroir).getByRole("link", { name: "Mon profil — Jean Dupont" })).toBeInTheDocument();
  });

  it("se resynchronise sur une écriture externe, sans passer par son propre picker (#323)", async () => {
    // Ce qui se passe réellement quand le bouton de la page profil
    // (`SelectAthleteButton`) écrit la sélection pendant qu'`AppNav` est déjà
    // monté ailleurs sur la page — aucune interaction avec le picker local ici.
    afficher(null);
    const rail = screen.getByRole("navigation", { name: "Navigation principale" });
    expect(within(rail).queryByRole("link", { name: /^Mon profil —/ })).not.toBeInTheDocument();

    act(() => writeAthlete({ id: 12, prenom: "Jean", nom: "Dupont" }));
    expect(await within(rail).findByRole("link", { name: "Mon profil — Jean Dupont" })).toBeInTheDocument();
    // La recherche reste là, en plus de la tuile — jamais remplacée.
    expect(within(rail).getByRole("button", { name: "Rechercher un athlète" })).toBeInTheDocument();

    act(() => clearAthlete());
    await waitFor(() =>
      expect(within(rail).queryByRole("link", { name: /^Mon profil —/ })).not.toBeInTheDocument(),
    );
  });
});

describe("AppNav — arborescence", () => {
  it("ne rend que les écrans livrés (#242)", async () => {
    afficher(null);
    await deplier();

    // Scopé au rail : la barre basse mobile (#482, NAV-4) porte les mêmes
    // libellés pour les mêmes destinations.
    const rail = screen.getByRole("navigation", { name: "Navigation principale" });
    expect(within(rail).getByRole("link", { name: "Tableau de bord" })).toHaveAttribute("href", "/dashboard");
    expect(within(rail).getByRole("link", { name: "Résultats" })).toHaveAttribute("href", "/resultats");

    // Une entrée `soon` reste déclarée dans `nav.config.ts` — feuille de route
    // de la navigation — mais n'est plus rendue nulle part.
    expect(screen.queryByText("Carte")).not.toBeInTheDocument();
    expect(screen.queryByText("À VENIR")).not.toBeInTheDocument();
  });

  it("rend « Club » comme un lien direct sur le rail replié, une seule destination livrée (#482, NAV-2)", async () => {
    afficher(null);
    // Scopé au rail : Task 6 y ajoute une barre basse mobile qui porte, elle
    // aussi, une entrée « Athlètes par saison ».
    const rail = screen.getByRole("navigation", { name: "Navigation principale" });

    // Plus de bouton dépliant pour une section à une seule destination : le
    // rail replié porte directement le lien.
    expect(within(rail).queryByRole("button", { name: "Club" })).not.toBeInTheDocument();
    const lien = within(rail).getByRole("link", { name: "Athlètes par saison" });
    expect(lien).toHaveAttribute("href", "/club/athletes");
    expect(screen.queryByLabelText("Carte")).not.toBeInTheDocument();

    await deplier();
    expect(within(rail).getByText("Club")).toBeInTheDocument();
    expect(within(rail).getByRole("link", { name: "Athlètes par saison" })).toHaveAttribute(
      "href",
      "/club/athletes",
    );
    expect(within(rail).queryByText("Espace club")).not.toBeInTheDocument();
  });

  it("garde le bouton dépliant pour une section à plusieurs destinations livrées (#482, NAV-2)", async () => {
    afficher(habilite("pending_providers:read", "batch:run"));

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Administration" })).toBeInTheDocument(),
    );
    expect(screen.queryByRole("link", { name: "Fournisseurs en attente" })).not.toBeInTheDocument();
  });

  it("marque l'entrée courante avec aria-current=\"page\"", async () => {
    afficher(null);
    await deplier();

    const rail = screen.getByRole("navigation", { name: "Navigation principale" });
    expect(within(rail).getByRole("link", { name: "Tableau de bord" })).toHaveAttribute("aria-current", "page");
    expect(within(rail).getByRole("link", { name: "Résultats" })).not.toHaveAttribute("aria-current");
  });

  it("cache Administration à un anonyme et la montre à un connecté", async () => {
    const { unmount } = afficher(null);
    await deplier();
    expect(screen.queryByText("Administration")).not.toBeInTheDocument();
    unmount();

    afficher(habilite("pending_providers:read", "courses:write"));
    await deplier();
    await waitFor(() => expect(screen.getByText("Administration")).toBeInTheDocument());
    expect(screen.getByRole("link", { name: "Fournisseurs en attente" })).toHaveAttribute(
      "href",
      "/admin/fournisseurs",
    );
    // Le libellé du rail est le titre de l'écran d'arrivée, pas un synonyme
    // (ADM-6) : « Gestion des courses » menait à une page intitulée « Épreuves ».
    expect(screen.getByRole("link", { name: "Épreuves" })).toHaveAttribute(
      "href",
      "/admin/courses",
    );
    // Les entrées d'échelon administrateur attendent #115 : rien ne l'attribue.
    expect(screen.queryByText("Feature flags")).not.toBeInTheDocument();
  });

  it("n'allume qu'une entrée d'administration à la fois", async () => {
    chemin.courant = "/admin/courses";
    afficher(habilite("pending_providers:read", "courses:write"));
    await deplier();

    // `isActive` teste `startsWith` : une entrée branchée sur `/admin` serait
    // allumée sur **tous** les écrans d'administration.
    await waitFor(() =>
      expect(screen.getByRole("link", { name: "Épreuves" })).toHaveAttribute(
        "aria-current",
        "page",
      ),
    );
    expect(
      screen.getByRole("link", { name: "Fournisseurs en attente" }),
    ).not.toHaveAttribute("aria-current");
  });

  it("n'annonce pas les fournisseurs à un connecté sans le pouvoir (#239)", async () => {
    // Ce que vit quelqu'un qui vient de se connecter et n'a pas encore de rôle :
    // le rail lui proposait un lien dont l'API rend 403. Annoncer un écran
    // refusé est le seul travail de `permission`.
    afficher(SESSION);
    await deplier();

    const rail = screen.getByRole("navigation", { name: "Navigation principale" });
    await waitFor(() => expect(within(rail).getByText("Résultats")).toBeInTheDocument());
    expect(
      screen.queryByRole("link", { name: "Fournisseurs en attente" }),
    ).not.toBeInTheDocument();
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
    // Scopé au rail : la barre basse mobile (#482, NAV-4) porte, elle aussi,
    // un « Résultats ».
    const rail = screen.getByRole("navigation", { name: "Navigation principale" });
    await waitFor(() => expect(within(rail).getByText("Résultats")).toBeInTheDocument());
    expect(screen.queryByText("Gestion des utilisateurs")).not.toBeInTheDocument();
    // « Administration » disparaît de même depuis qu'« Épreuves » porte un
    // pouvoir : c'était la seule entrée de la section à n'en porter aucun,
    // donc la seule proposée à qui n'y peut rien faire (ADM-6).
    expect(screen.queryByText("Administration")).not.toBeInTheDocument();
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
    // `startsWith` allumait l'entrée des fournisseurs en même temps que l'écran
    // des accès. Un href de la nav désigne **un** écran, pas une famille : les
    // écrans à venir vivront eux aussi sous `/admin/`.
    chemin.courant = "/admin/acces";
    afficher(habilite("allowed_emails:manage", "pending_providers:read"));
    await deplier();

    const courant = await screen.findByRole("link", { name: "Accès au back-office" });
    expect(courant).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Fournisseurs en attente" })).not.toHaveAttribute(
      "aria-current",
    );
  });

  it("ne porte que les entrées dont le pouvoir est détenu", async () => {
    // Composer les droits d'un rôle et autoriser une adresse sont deux pouvoirs
    // distincts : porter l'un ne doit pas annoncer l'écran de l'autre.
    afficher(habilite("roles:write"));
    await deplier();
    await waitFor(() => expect(screen.getByText("Gestion des utilisateurs")).toBeInTheDocument());

    expect(screen.getByRole("link", { name: "Droits des rôles" })).toBeInTheDocument();
    expect(screen.queryByText("Accès au back-office")).not.toBeInTheDocument();
  });

  it("ouvre « Droits des rôles » à qui porte roles:write (#240)", async () => {
    afficher(habilite("roles:write"));
    await deplier();
    await waitFor(() => expect(screen.getByText("Gestion des utilisateurs")).toBeInTheDocument());

    expect(screen.getByRole("link", { name: "Droits des rôles" })).toHaveAttribute(
      "href",
      "/admin/droits",
    );
  });

  it("garde la section fermée à qui ne porte aucun de ses pouvoirs", async () => {
    // La section entière disparaît quand le filtrage la vide — c'est `AppNav`
    // qui retire les sections vides, pas `nav.config.ts`.
    afficher(habilite("courses:write"));
    await deplier();
    await waitFor(() => expect(screen.getByText("Administration")).toBeInTheDocument());

    expect(screen.queryByText("Gestion des utilisateurs")).not.toBeInTheDocument();
  });

  it("ne rend pas les écrans non livrés, même à qui en porte le pouvoir (#242)", async () => {
    afficher(
      habilite(
        "allowed_emails:manage",
        "roles:assign",
        "roles:write",
        "groups:assign",
        "quality:override",
      ),
    );
    await deplier();
    await waitFor(() => expect(screen.getByText("Gestion des utilisateurs")).toBeInTheDocument());

    // « Rôles des utilisateurs » (#239), « Droits des rôles » (#240) et
    // « Groupes d'appartenance » (#241) sont livrés : ils mènent quelque part.
    expect(
      screen.getByRole("link", { name: "Rôles des utilisateurs" }),
    ).toHaveAttribute("href", "/admin/utilisateurs");
    expect(
      screen.getByRole("link", { name: "Droits des rôles" }),
    ).toHaveAttribute("href", "/admin/droits");
    expect(
      screen.getByRole("link", { name: "Groupes d'appartenance" }),
    ).toHaveAttribute("href", "/admin/groupes");

    // « Revalidation qualité » est livrée depuis #119 : elle mène quelque part.
    expect(
      screen.getByRole("link", { name: "Revalidation qualité" }),
    ).toHaveAttribute("href", "/admin/quality");

    // « Bénévolat », elle, reste `soon` : toujours pas de lien à afficher.
    expect(screen.queryByText("Bénévolat")).not.toBeInTheDocument();
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

describe("badge de la file de revalidation (#119)", () => {
  beforeEach(() => {
    countCourses.mockReset();
  });

  it("affiche le nombre d'épreuves à revalider sur son entrée", async () => {
    countCourses.mockResolvedValue({ total: 4 });
    afficher(habilite("quality:override"));
    await deplier();

    const entree = await screen.findByRole("link", { name: /revalidation qualité/i });
    expect(await within(entree).findByText("4")).toBeInTheDocument();
  });

  it("n'affiche aucun badge quand la file est vide", async () => {
    countCourses.mockResolvedValue({ total: 0 });
    afficher(habilite("quality:override"));
    await deplier();

    const entree = await screen.findByRole("link", { name: /revalidation qualité/i });
    await waitFor(() => expect(countCourses).toHaveBeenCalled());
    expect(within(entree).queryByText("0")).not.toBeInTheDocument();
  });

  it("n'émet aucun comptage pour qui ne porte pas le pouvoir", async () => {
    afficher(habilite("feedback:read"));
    await deplier();

    await screen.findByRole("link", { name: /retours utilisateurs/i });
    expect(countCourses).not.toHaveBeenCalled();
  });

  it("porte un nom accessible explicite, pas seulement le chiffre nu", async () => {
    countCourses.mockResolvedValue({ total: 4 });
    afficher(habilite("quality:override"));
    await deplier();

    // ARIA 1.2 interdit de nommer un `<span>` (rôle `generic`) par
    // `aria-label` : le nom accessible passe par un texte `sr-only` dédié, la
    // pastille chiffrée restant purement décorative.
    expect(await screen.findByText("4 épreuves à revalider")).toHaveClass("sr-only");
    expect(screen.getByText("4")).toHaveAttribute("aria-hidden", "true");
  });
});

describe("AppNav — infobulles du rail replié remplacent les title (#482, NAV-2)", () => {
  it("affiche une infobulle « Se connecter » au survol du bouton replié", async () => {
    afficher(null);
    const rail = screen.getByRole("navigation", { name: "Navigation principale" });
    const bouton = within(rail).getByRole("button", { name: "Se connecter" });

    await userEvent.hover(bouton);
    expect(await screen.findByRole("tooltip", { name: "Se connecter" })).toBeInTheDocument();
  });

  it("affiche la même infobulle au focus clavier, pas seulement au survol", async () => {
    afficher(null);
    const rail = screen.getByRole("navigation", { name: "Navigation principale" });
    const bouton = within(rail).getByRole("button", { name: "Se connecter" });

    act(() => bouton.focus());
    expect(await screen.findByRole("tooltip", { name: "Se connecter" })).toBeInTheDocument();
  });

  it("n'affiche plus aucune infobulle sur ce bouton une fois le rail déplié", async () => {
    afficher(null, { initialExpanded: true });
    const rail = screen.getByRole("navigation", { name: "Navigation principale" });
    const bouton = within(rail).getByRole("button", { name: "Se connecter" });

    await userEvent.hover(bouton);
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  it("porte une infobulle sur le lien « Ajouter une épreuve » replié", async () => {
    afficher(null);
    const rail = screen.getByRole("navigation", { name: "Navigation principale" });
    const lien = within(rail).getByRole("link", { name: "Ajouter une épreuve" });

    await userEvent.hover(lien);
    expect(await screen.findByRole("tooltip", { name: "Ajouter une épreuve" })).toBeInTheDocument();
  });

  it("porte une infobulle sur le bouton « Rechercher un athlète » replié", async () => {
    afficher(null);
    const rail = screen.getByRole("navigation", { name: "Navigation principale" });
    const bouton = within(rail).getByRole("button", { name: "Rechercher un athlète" });

    await userEvent.hover(bouton);
    // Le contenu de l'infobulle reprend le raccourci clavier, comme le
    // faisait le `title` natif qu'elle remplace — seul l'`aria-label` du
    // bouton reste sobre.
    expect(await screen.findByRole("tooltip", { name: "Rechercher un athlète (Ctrl K)" })).toBeInTheDocument();
  });

  it("porte une infobulle « Mon profil » sur la tuile de l'athlète retenu, repliée", async () => {
    window.localStorage.setItem("tcn-athlete", JSON.stringify({ id: 12, prenom: "Jean", nom: "Dupont" }));
    afficher(null);
    const avatar = await screen.findByRole("link", { name: "Mon profil — Jean Dupont" });

    await userEvent.hover(avatar);
    expect(await screen.findByRole("tooltip", { name: "Mon profil" })).toBeInTheDocument();
  });

  it("porte une infobulle sur la tuile de catégorie repliée (« Administration »)", async () => {
    afficher(habilite("pending_providers:read", "batch:run"));
    const bouton = await screen.findByRole("button", { name: "Administration" });

    await userEvent.hover(bouton);
    expect(await screen.findByRole("tooltip", { name: "Administration" })).toBeInTheDocument();
  });

  it("porte une infobulle sur une entrée repliée du rail (« Tableau de bord »)", async () => {
    afficher(null);
    const rail = screen.getByRole("navigation", { name: "Navigation principale" });
    const lien = within(rail).getByRole("link", { name: "Tableau de bord" });

    await userEvent.hover(lien);
    expect(await screen.findByRole("tooltip", { name: "Tableau de bord" })).toBeInTheDocument();
  });
});

describe("AppNav — barre basse mobile (#482, NAV-4)", () => {
  it("porte les trois destinations publiques, avec libellé visible", () => {
    afficher(null);

    const barre = screen.getByRole("navigation", { name: "Navigation" });
    expect(within(barre).getByRole("link", { name: "Tableau de bord" })).toHaveAttribute("href", "/dashboard");
    expect(within(barre).getByRole("link", { name: "Résultats" })).toHaveAttribute("href", "/resultats");
    expect(within(barre).getByRole("link", { name: "Athlètes par saison" })).toHaveAttribute(
      "href",
      "/club/athletes",
    );
  });

  it("marque la destination courante avec aria-current=\"page\"", () => {
    afficher(null);

    const barre = screen.getByRole("navigation", { name: "Navigation" });
    expect(within(barre).getByRole("link", { name: "Tableau de bord" })).toHaveAttribute("aria-current", "page");
    expect(within(barre).getByRole("link", { name: "Résultats" })).not.toHaveAttribute("aria-current");
  });

  it("ne porte aucune destination privée, connecté ou non", async () => {
    // Deux pouvoirs, pas un seul : une seule destination livrée ferait rendre
    // « Administration » en lien direct plutôt qu'en tuile de catégorie
    // (#482, NAV-2). Attend la tuile par son nom accessible, pas par un texte
    // visible : repliée, seule l'icône est rendue, le libellé ne vit que
    // dans l'`aria-label` du bouton.
    afficher(habilite("pending_providers:read", "batch:run"));
    await waitFor(() => expect(screen.getByRole("button", { name: "Administration" })).toBeInTheDocument());

    const barre = screen.getByRole("navigation", { name: "Navigation" });
    expect(within(barre).queryByRole("link", { name: "Fournisseurs en attente" })).not.toBeInTheDocument();
  });
});
