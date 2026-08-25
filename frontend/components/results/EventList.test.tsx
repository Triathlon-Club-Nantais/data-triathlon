import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// jsdom ne fournit pas IntersectionObserver, requis par le défilement infini
// dès que `hasNextPage` est vrai.
class IntersectionObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.IntersectionObserver = IntersectionObserverStub as unknown as typeof IntersectionObserver;

const push = vi.fn();
let searchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, refresh: vi.fn() }),
  useSearchParams: () => searchParams,
}));

const eventsMock = vi.hoisted(() => ({
  value: {} as ReturnType<typeof Object>,
}));

vi.mock("@/lib/queries/events", () => ({
  EVENTS_PAGE_SIZE: 30,
  useInfiniteEvents: () => eventsMock.value,
}));

import { EventList } from "./EventList";

function setEvents(value: unknown) {
  eventsMock.value = value as never;
}

function renderList(filters = {}) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <EventList filters={filters} />
    </QueryClientProvider>,
  );
}

describe("EventList", () => {
  beforeEach(() => {
    searchParams = new URLSearchParams();
    push.mockClear();
  });

  it("rend chaque épreuve comme un lien vers sa fiche course", () => {
    setEvents({
      data: {
        pages: [
          {
            items: [
              {
                id: 14,
                event_name: "Tri de Nantes",
                event_type: "triathlon-m",
                event_date: "2026-05-16",
                is_relay: false,
                total: 42,
                tcn_count: 3,
              },
            ],
            total_events: 1,
            total_participations: 42,
          },
        ],
      },
      fetchNextPage: vi.fn(),
      hasNextPage: false,
      isFetchingNextPage: false,
      isLoading: false,
    });

    renderList();

    const link = screen.getByRole("link", { name: /Tri de Nantes/ });
    expect(link).toHaveAttribute("href", "/courses/14");
    // Métadonnées conservées dans la ligne. Depuis #481 la ligne **est** le
    // `<tr>`, et le lien n'occupe que la cellule du nom : c'est la ligne qu'on
    // interroge, pas l'ancre.
    const ligne = link.closest("tr")!;
    expect(ligne).toHaveTextContent("Triathlon M");
    expect(ligne).toHaveTextContent("42 résultats");
    expect(ligne).toHaveTextContent("3");
  });

  it("n'affiche plus de bouton de suppression ni d'accordéon", () => {
    setEvents({
      data: {
        pages: [
          {
            items: [
              {
                id: 14,
                event_name: "Tri de Nantes",
                event_type: "triathlon-m",
                event_date: "2026-05-16",
                is_relay: false,
                total: 42,
                tcn_count: 3,
              },
            ],
            total_events: 1,
            total_participations: 42,
          },
        ],
      },
      fetchNextPage: vi.fn(),
      hasNextPage: false,
      isFetchingNextPage: false,
      isLoading: false,
    });

    renderList();

    expect(screen.queryByRole("button", { name: /supprimer/i })).toBeNull();
    // L'épreuve est un lien plein, plus un trigger d'accordéon dépliable.
    expect(screen.queryByRole("button", { name: /Tri de Nantes/i })).toBeNull();
    expect(screen.getByRole("link", { name: /Tri de Nantes/ })).toBeInTheDocument();
  });

  it("affiche « (Relais) » dans le nom d'une épreuve relais", () => {
    setEvents({
      data: {
        pages: [
          {
            items: [
              {
                id: 2,
                event_name: "Triathlon de Nantes",
                event_type: "triathlon-m",
                event_date: "2026-06-01",
                is_relay: true,
                total: 10,
                tcn_count: 2,
              },
            ],
            total_events: 1,
            total_participations: 10,
          },
        ],
      },
      fetchNextPage: vi.fn(),
      hasNextPage: false,
      isFetchingNextPage: false,
      isLoading: false,
    });

    renderList();

    expect(screen.getByText("Triathlon de Nantes (Relais)")).toBeInTheDocument();
  });

  // Issue #78 : sous cette largeur, la piste « Épreuve » était écrasée et son
  // texte débordait sur la colonne « Type ».
  it("réserve au conteneur scrollable la largeur exigée par ses colonnes", () => {
    setEvents({
      data: {
        pages: [
          {
            items: [
              {
                id: 14,
                event_name: "Triathlon Open Quiberon 2026 - Dimanche",
                event_type: "triathlon-s",
                event_date: "2026-06-21",
                is_relay: false,
                total: 462,
                tcn_count: 3,
              },
            ],
            total_events: 1,
            total_participations: 462,
          },
        ],
      },
      fetchNextPage: vi.fn(),
      hasNextPage: false,
      isFetchingNextPage: false,
      isLoading: false,
    });

    renderList();

    // La ligne est le `<tr>` depuis #481 : c'est lui qui porte la grille.
    const row = screen.getByRole("link", { name: /Quiberon/ }).closest("tr")!;
    const style = getComputedStyle(row);
    // Une valeur px par piste : sa largeur fixe, ou la borne basse de son minmax.
    const tracks = [...style.gridTemplateColumns.matchAll(/(\d+)px/g)].map((m) => Number(m[1]));
    // Sans cette assertion, un `gridTemplateColumns` illisible passerait pour
    // une grille sans colonne — et le test réussirait sans rien contraindre.
    expect(tracks).toHaveLength(7); // Date | Épreuve | Type | Format | Résultats | TCN | →
    const required =
      tracks.reduce((a, b) => a + b, 0) +
      parseFloat(style.columnGap) * (tracks.length - 1) +
      parseFloat(style.paddingLeft) +
      parseFloat(style.paddingRight);

    // Le conteneur à largeur plancher est le parent du `<table>`, la ligne
    // étant désormais deux niveaux plus bas (`<tbody>` puis `<tr>`).
    const scrollBody = row.closest("table")!.parentElement!;
    expect(parseFloat(getComputedStyle(scrollBody).minWidth)).toBeGreaterThanOrEqual(required);
  });

  it("affiche un état vide quand aucune épreuve", () => {
    setEvents({
      data: { pages: [{ items: [], total_events: 0, total_participations: 0 }] },
      fetchNextPage: vi.fn(),
      hasNextPage: false,
      isFetchingNextPage: false,
      isLoading: false,
    });

    renderList();
    expect(screen.getByText("Aucun résultat")).toBeInTheDocument();
  });

  // WCAG 4.1.3 (#477) : filtrer/trier remplace la liste sans annonce.
  it("annonce le décompte d'épreuves et de résultats dans une région role=status", () => {
    setEvents({
      data: {
        pages: [
          {
            items: [
              {
                id: 14,
                event_name: "Tri de Nantes",
                event_type: "triathlon-m",
                event_date: "2026-05-16",
                is_relay: false,
                total: 42,
                tcn_count: 3,
              },
            ],
            total_events: 48,
            total_participations: 312,
          },
        ],
      },
      fetchNextPage: vi.fn(),
      hasNextPage: false,
      isFetchingNextPage: false,
      isLoading: false,
    });

    renderList();

    expect(screen.getByRole("status")).toHaveTextContent("48 épreuves, 312 résultats");
  });

  it("garde la région d'annonce montée quand un filtre ne laisse plus aucune épreuve (revue de code)", () => {
    // Avant la revue : `AnnonceStatut` était rendu après le retour anticipé sur
    // liste vide, donc absente du DOM précisément quand un filtre venant de
    // tout effacer aurait le plus besoin de le dire.
    setEvents({
      data: { pages: [{ items: [], total_events: 0, total_participations: 0 }] },
      fetchNextPage: vi.fn(),
      hasNextPage: false,
      isFetchingNextPage: false,
      isLoading: false,
    });

    renderList();

    expect(screen.getByRole("status")).toHaveTextContent("0 épreuve, 0 résultat");
  });

  it("réannonce quand le défilement infini charge une page supplémentaire (revue de code)", () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const page = (id: number) => ({
      id,
      event_name: `Épreuve ${id}`,
      event_type: "triathlon-m",
      event_date: "2026-05-16",
      is_relay: false,
      total: 42,
      tcn_count: 0,
    });
    setEvents({
      data: { pages: [{ items: [page(1)], total_events: 48, total_participations: 312 }] },
      fetchNextPage: vi.fn(),
      hasNextPage: true,
      isFetchingNextPage: false,
      isLoading: false,
    });
    const { rerender } = render(
      <QueryClientProvider client={qc}>
        <EventList filters={{}} />
      </QueryClientProvider>,
    );
    expect(screen.getByRole("status")).toHaveTextContent("48 épreuves, 312 résultats, 1 affichée");

    setEvents({
      data: {
        pages: [
          { items: [page(1)], total_events: 48, total_participations: 312 },
          { items: [page(2)], total_events: 48, total_participations: 312 },
        ],
      },
      fetchNextPage: vi.fn(),
      hasNextPage: false,
      isFetchingNextPage: false,
      isLoading: false,
    });
    rerender(
      <QueryClientProvider client={qc}>
        <EventList filters={{}} />
      </QueryClientProvider>,
    );

    expect(screen.getByRole("status")).toHaveTextContent("48 épreuves, 312 résultats, 2 affichées");
  });
});

// Issue #463 : quinze épreuves d'un même week-end partagent 49 caractères de
// préfixe ; la liste plate obligeait à lire jusqu'au 60ᵉ pour les distinguer.
describe("EventList — regroupement par compétition parente (#463)", () => {
  const PREFIXE = "MEDOC ATLANTIQUE FRENCHMAN Triathlon Carcans 2026";
  const sousEpreuve = (id: number, suffixe: string, total: number, tcn: number) => ({
    id,
    event_name: `${PREFIXE} - ${suffixe}`,
    event_type: "triathlon-s",
    event_date: "2026-06-13",
    is_relay: false,
    total,
    tcn_count: tcn,
  });

  function setGroupe() {
    setEvents({
      data: {
        pages: [
          {
            items: [
              sousEpreuve(1, "Frenchkid Aquathlon - 2013/2014 - Fille", 120, 2),
              sousEpreuve(2, "Frenchkid Aquathlon - 2013/2014 - Garçon", 80, 1),
            ],
            total_events: 2,
            total_participations: 200,
          },
        ],
      },
      fetchNextPage: vi.fn(),
      hasNextPage: false,
      isFetchingNextPage: false,
      isLoading: false,
    });
  }

  it("replie plusieurs épreuves d'une même compétition sous une ligne dépliable", () => {
    setGroupe();
    renderList();

    const entete = screen.getByRole("button", { name: new RegExp(PREFIXE) });
    expect(entete).toHaveAttribute("aria-expanded", "false");
    // Le bouton ne porte plus que le nom de la compétition : le reste de la
    // ligne vit dans les cellules voisines depuis #481.
    expect(entete.closest("tr")).toHaveTextContent("2 épreuves");
    expect(screen.queryByRole("link", { name: /Fille/ })).toBeNull();
  });

  it("additionne résultats et TCN des épreuves chargées sur la ligne de compétition", () => {
    setGroupe();
    renderList();

    const ligne = screen.getByRole("button", { name: new RegExp(PREFIXE) }).closest("tr")!;
    expect(ligne).toHaveTextContent("200 résultats");
    expect(ligne).toHaveTextContent("3");
  });

  it("déplie la compétition et n'affiche que la part distinctive de chaque épreuve", async () => {
    setGroupe();
    renderList();

    await userEvent.click(screen.getByRole("button", { name: new RegExp(PREFIXE) }));

    const lien = screen.getByRole("link", { name: /2013\/2014 - Fille/ });
    expect(lien).toHaveAttribute("href", "/courses/1");
    // Le préfixe commun est porté par la ligne de groupe, pas répété 15 fois.
    expect(lien).not.toHaveTextContent(PREFIXE);
  });

  it("laisse une épreuve isolée en lien direct, sans ligne de groupe", () => {
    setEvents({
      data: {
        pages: [
          {
            items: [
              {
                id: 14,
                event_name: "Tri de Nantes",
                event_type: "triathlon-m",
                event_date: "2026-05-16",
                is_relay: false,
                total: 42,
                tcn_count: 3,
              },
            ],
            total_events: 1,
            total_participations: 42,
          },
        ],
      },
      fetchNextPage: vi.fn(),
      hasNextPage: false,
      isFetchingNextPage: false,
      isLoading: false,
    });

    renderList();

    expect(screen.queryByRole("button", { name: /Tri de Nantes/ })).toBeNull();
    expect(screen.getByRole("link", { name: /Tri de Nantes/ })).toHaveAttribute(
      "href",
      "/courses/14",
    );
  });
});

describe("EventList — annonce du repliement (#463, WCAG 4.1.3)", () => {
  const PREFIXE = "MEDOC ATLANTIQUE FRENCHMAN Triathlon Carcans 2026";

  function setDeuxSousEpreuves() {
    setEvents({
      data: {
        pages: [
          {
            items: [1, 2].map((id) => ({
              id,
              event_name: `${PREFIXE} - Épreuve ${id}`,
              event_type: "triathlon-s",
              event_date: "2026-06-13",
              is_relay: false,
              total: 100,
              tcn_count: 1,
            })),
            total_events: 2,
            total_participations: 200,
          },
        ],
      },
      fetchNextPage: vi.fn(),
      hasNextPage: false,
      isFetchingNextPage: false,
      isLoading: false,
    });
  }

  it("signale les compétitions repliées, que le décompte d'épreuves chargées ne dit pas", () => {
    setDeuxSousEpreuves();
    renderList();

    expect(screen.getByRole("status")).toHaveTextContent(
      "2 épreuves, 200 résultats, 2 affichées dans 1 compétition repliée",
    );
  });

  it("retire la mention quand la compétition est dépliée", async () => {
    setDeuxSousEpreuves();
    renderList();

    await userEvent.click(screen.getByRole("button", { name: new RegExp(PREFIXE) }));

    expect(screen.getByRole("status")).toHaveTextContent("2 épreuves, 200 résultats, 2 affichées");
    expect(screen.getByRole("status")).not.toHaveTextContent("repliée");
  });

  // ── Structure de tableau (#481, A11Y-3) ────────────────────────────────────

  it("s'annonce comme un tableau et nomme ses colonnes, la dernière restant sans libellé", () => {
    setDeuxSousEpreuves();
    renderList();

    expect(screen.getByRole("table")).toBeInTheDocument();
    for (const nom of ["Date", "Épreuve", "Type", "Format", "Résultats"]) {
      expect(screen.getByRole("columnheader", { name: nom })).toBeInTheDocument();
    }
    // La 7e colonne est nommée en `sr-only` : un `<th>` vide est une colonne
    // anonyme, et sa flèche était annoncée à chaque ligne (revue UI/UX #481).
    expect(screen.getAllByRole("columnheader")).toHaveLength(7);
    expect(screen.getByRole("columnheader", { name: "Ouvrir" })).toBeInTheDocument();
  });

  it("expose autant de cellules sur une ligne de groupe que de colonnes déclarées", () => {
    // La cellule du chevron portait `aria-hidden` : l'arbre d'accessibilité la
    // supprimait, et la ligne de groupe annonçait 6 cellules pour 7 colonnes —
    // l'incohérence même que la promesse 1.3.1 du lot interdit (revue de code
    // #481). Le glyphe reste décoratif, mais c'est le `<span>` qui se cache.
    setDeuxSousEpreuves();
    renderList();

    const ligne = screen.getByRole("button", { name: new RegExp(PREFIXE) }).closest("tr")!;
    expect(within(ligne).getAllByRole("cell")).toHaveLength(7);
  });

  it("garde la ligne de groupe en bouton — elle déplie, elle ne navigue pas", () => {
    // En faire un lien serait la régression 4.1.2 qu'on corrige ailleurs.
    setDeuxSousEpreuves();
    renderList();

    const groupe = screen.getByRole("button", { name: new RegExp(PREFIXE) });
    expect(groupe).toHaveAttribute("aria-expanded", "false");
    expect(groupe.closest("tr")).not.toBeNull();
  });

  it("révèle les épreuves d'une compétition dans le rowgroup de son groupe", async () => {
    setDeuxSousEpreuves();
    renderList();

    const corpsAvant = screen.getAllByRole("rowgroup").filter((g) => g.tagName === "TBODY");
    expect(corpsAvant).toHaveLength(1);
    expect(within(corpsAvant[0]).getAllByRole("row")).toHaveLength(1);

    await userEvent.click(screen.getByRole("button", { name: new RegExp(PREFIXE) }));

    const corpsApres = screen.getAllByRole("rowgroup").filter((g) => g.tagName === "TBODY");
    expect(within(corpsApres[0]).getAllByRole("row")).toHaveLength(3); // groupe + 2 épreuves
  });

  it("n'offre qu'un arrêt clavier par ligne", () => {
    setDeuxSousEpreuves();
    renderList();

    for (const ligne of screen.getAllByRole("row")) {
      expect(
        ligne.querySelectorAll("a[href], button, input, select, textarea").length,
      ).toBeLessThanOrEqual(1);
    }
  });

  it("ne rend aucun tableau sur une liste vide : l'écran sort avant la carte", () => {
    setEvents({
      data: { pages: [{ items: [], total_events: 0, total_participations: 0 }] },
      fetchNextPage: vi.fn(),
      hasNextPage: false,
      isFetchingNextPage: false,
      isLoading: false,
    });
    renderList();

    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.getByText("Aucun résultat")).toBeInTheDocument();
  });

  // ── Fiabilité en liste (#486, RES-10) ────────────────────────────────────

  function unePage(items: unknown[]) {
    setEvents({
      data: { pages: [{ items, total_events: items.length, total_participations: 42 }] },
      fetchNextPage: vi.fn(),
      hasNextPage: false,
      isFetchingNextPage: false,
      isLoading: false,
    });
  }

  const EPREUVE = {
    id: 14,
    event_name: "Tri de Nantes",
    event_type: "triathlon-m",
    event_date: "2026-05-16",
    is_relay: false,
    total: 42,
    tcn_count: 3,
  };

  it("marque une épreuve à anomalies, dans les mots du reste du produit", () => {
    unePage([{ ...EPREUVE, is_reliable: false, quality_issues: { rank_gap: 2 } }]);

    renderList();

    // Même vocabulaire que la page épreuve et que le profil athlète : la source
    // est `lib/quality.ts`, et elle ne doit pas se dédoubler.
    expect(
      screen.getByRole("img", { name: /2 trous dans le classement/ }),
    ).toBeInTheDocument();
  });

  it("ne marque pas une épreuve saine", () => {
    unePage([{ ...EPREUVE, is_reliable: true, quality_issues: null }]);

    renderList();

    expect(screen.queryByRole("img", { name: /Données douteuses/ })).not.toBeInTheDocument();
  });

  it("ne marque pas une épreuve jamais évaluée — `null` n'est pas un verdict", () => {
    unePage([{ ...EPREUVE, is_reliable: null, quality_issues: null }]);

    renderList();

    expect(screen.queryByRole("img", { name: /Données douteuses/ })).not.toBeInTheDocument();
  });
});

// Issue #577 : pendant une recherche d'épreuve, le backend classe toujours par
// similarité en tête (`event_name` déclenche `similarity(Course.name, …)`,
// `_events_order`) — le sélecteur doit le dire plutôt que prétendre appliquer
// le tri affiché.
describe("EventList — entrée « Pertinence » pendant une recherche d'épreuve (#577)", () => {
  function setUnEvenement() {
    setEvents({
      data: {
        pages: [
          {
            items: [
              {
                id: 14,
                event_name: "Tri de Nantes",
                event_type: "triathlon-m",
                event_date: "2026-05-16",
                is_relay: false,
                total: 42,
                tcn_count: 3,
              },
            ],
            total_events: 1,
            total_participations: 42,
          },
        ],
      },
      fetchNextPage: vi.fn(),
      hasNextPage: false,
      isFetchingNextPage: false,
      isLoading: false,
    });
  }

  it("n'offre pas « Pertinence » hors recherche d'épreuve", async () => {
    setUnEvenement();
    renderList();

    await userEvent.click(screen.getByRole("combobox"));
    const options = (await screen.findAllByRole("option")).map((o) => o.textContent);
    expect(options).toEqual(["Date (récent)", "Date (ancien)", "Nom"]);
  });

  it("sélectionne « Pertinence » par défaut dès qu'une recherche d'épreuve est active", async () => {
    searchParams = new URLSearchParams("event_name=nantes");
    setUnEvenement();
    renderList();

    expect(screen.getByRole("combobox")).toHaveTextContent("Pertinence");

    await userEvent.click(screen.getByRole("combobox"));
    const options = (await screen.findAllByRole("option")).map((o) => o.textContent);
    expect(options).toEqual(["Pertinence", "Date (récent)", "Date (ancien)", "Nom"]);
  });

  it("garde le tri choisi affiché quand il a été explicitement posé pendant une recherche", () => {
    // La similarité reste prioritaire côté backend (_events_order) — ce tri ne
    // fait que départager — mais un choix explicite reste dit tel quel, pas
    // ramené à « Pertinence ».
    searchParams = new URLSearchParams("event_name=nantes&sort=date_asc");
    setUnEvenement();
    renderList();

    expect(screen.getByRole("combobox")).toHaveTextContent("Date (ancien)");
  });

  it("distingue un « Date (récent) » explicite de l'absence de tri, alors que la valeur backend est la même", () => {
    // `date_desc` est à la fois la valeur explicite de « Date (récent) » et le
    // défaut appliqué en l'absence de `sort` : seule la présence du paramètre
    // dans l'URL distingue les deux — pas sa valeur (revue de code #577).
    searchParams = new URLSearchParams("event_name=nantes&sort=date_desc");
    setUnEvenement();
    renderList();

    expect(screen.getByRole("combobox")).toHaveTextContent("Date (récent)");
    expect(screen.getByRole("combobox")).not.toHaveTextContent("Pertinence");
  });

  it("choisir « Pertinence » retire le paramètre sort de l'URL sans toucher aux autres", async () => {
    searchParams = new URLSearchParams("event_name=nantes&sort=name");
    setUnEvenement();
    renderList();

    await userEvent.click(screen.getByRole("combobox"));
    await userEvent.click(await screen.findByRole("option", { name: "Pertinence" }));

    expect(push).toHaveBeenCalledWith("/resultats?event_name=nantes");
  });

  it("revient au tri par défaut, sans « Pertinence », quand la recherche d'épreuve se vide", () => {
    searchParams = new URLSearchParams();
    setUnEvenement();
    renderList();

    expect(screen.getByRole("combobox")).toHaveTextContent("Date (récent)");
    expect(screen.getByRole("combobox")).not.toHaveTextContent("Pertinence");
  });
});
