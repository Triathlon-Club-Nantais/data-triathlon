import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { SeasonSelector, SeasonTags, buildSeasonsHref } from "./SeasonSelector";
import { currentSeason, seasonLabel } from "@/lib/utils/season";
import type { Season } from "@/lib/types";

// Query string mutable : la mise en page des tags (#445) ne s'observe qu'avec
// plusieurs saisons sélectionnées, donc `?seasons=` doit pouvoir varier d'un
// test à l'autre.
const url = vi.hoisted(() => ({ qs: "" }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => "/dashboard",
  useSearchParams: () => new URLSearchParams(url.qs),
}));

beforeEach(() => {
  url.qs = "";
});

const CS = currentSeason();
const SEASONS: Season[] = [
  { start_year: CS, label: seasonLabel(CS), event_count: 0, participation_count: 0, is_current: true },
  { start_year: 2023, label: "Saison 2023 — 2024", event_count: 3, participation_count: 12, is_current: false },
];

describe("buildSeasonsHref", () => {
  it("omet le paramètre quand seule la saison en cours est sélectionnée", () => {
    // saison en cours par défaut → pas de ?seasons
    const href = buildSeasonsHref([currentSeason()], undefined, "/dashboard");
    expect(href === "/dashboard" || href === "/dashboard?").toBe(true);
    expect(href).not.toContain("seasons=");
  });
  it("sérialise plusieurs saisons et préserve le scope", () => {
    const href = buildSeasonsHref([2025, 2023], "club", "/dashboard");
    expect(href).toContain("seasons=2025%2C2023");
    expect(href).toContain("scope=club");
  });
  it("respecte le pathname fourni (#274 — réutilisé hors /dashboard)", () => {
    const href = buildSeasonsHref([2023], undefined, "/club/athletes");
    expect(href).toBe("/club/athletes?seasons=2023");
  });
});

describe("SeasonSelector", () => {
  it("affiche par défaut le libellé de la saison en cours", () => {
    render(<SeasonSelector seasons={SEASONS} />);
    expect(screen.getByText(new RegExp(`Saison ${currentSeason()}`))).toBeInTheDocument();
  });

  it("porte la variante Tailwind data-pending:opacity-70 dès le rendu initial", () => {
    // Le trajet vers /dashboard traverse le serveur (issue #345) : l'élément
    // qui recevra `data-pending` pendant la transition doit déjà porter la
    // classe qui l'exploite, sans quoi l'attribut ne sert à rien (piège
    // relevé sur RankTypeToggle, qui ne portait qu'un `style` en ligne).
    render(<SeasonSelector seasons={SEASONS} />);
    expect(screen.getByLabelText("Choisir les saisons").className).toContain(
      "data-pending:opacity-70"
    );
  });

  it("porte aussi le signal sur la liste ouverte du popover, là où l'utilisateur coche", () => {
    // Le popover reste ouvert pendant tout le cochage : une fois ouvert,
    // l'utilisateur ne regarde plus le déclencheur mais la liste. Le
    // conteneur du popover doit donc porter, lui aussi, la variante qui lit
    // `data-pending` (revue UI/UX de #345 : le signal posé uniquement sur le
    // déclencheur répond mal à « l'utilisateur voit-il que son clic a été
    // pris en compte ? »).
    render(<SeasonSelector seasons={SEASONS} />);
    fireEvent.click(screen.getByLabelText("Choisir les saisons"));
    const list = screen.getByText("Saison 2023 — 2024").closest("[data-slot='popover-content']");
    expect(list).not.toBeNull();
    expect(list?.className).toContain("data-pending:opacity-70");
  });
});

describe("SeasonSelector — le déclencheur ne porte plus les tags (#445)", () => {
  it("ne rend qu'un bouton, sans conteneur ni tag, même en multi-saisons", () => {
    // Les tags rendus à côté du déclencheur élargissaient la barre d'outils
    // jusqu'à la faire basculer sous le titre, tout à gauche : c'est ce qui
    // déplaçait les boutons de sélection dès la deuxième saison cochée. Ils
    // vivent désormais dans `SeasonTags`, que la page place hors de la barre.
    url.qs = `seasons=${CS},2023`;
    render(<SeasonSelector seasons={SEASONS} />);

    expect(screen.queryByTestId("season-tags")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Choisir les saisons")).toHaveTextContent(
      "2 saisons sélectionnées",
    );
  });
});

describe("SeasonTags (#445)", () => {
  it("ne rend rien quand une seule saison est sélectionnée — le déclencheur en porte déjà le libellé", () => {
    const { container } = render(<SeasonTags seasons={SEASONS} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("nomme chaque saison sélectionnée", () => {
    url.qs = `seasons=${CS},2023`;
    render(<SeasonTags seasons={SEASONS} />);

    const tags = screen.getByTestId("season-tags");
    expect(tags).toHaveTextContent(seasonLabel(CS));
    expect(tags).toHaveTextContent("Saison 2023 — 2024");
  });

  it("se nomme, la ligne étant détachée de son déclencheur (revue UI/UX)", () => {
    // Séparée du déclencheur par l'en-tête, la ligne perd le rattachement que
    // la proximité visuelle assurait : un lecteur d'écran énumérait des
    // libellés de saison sans rien pour les relier au bouton, qui ne dit que
    // « 2 saisons sélectionnées ». `role="group"` parce qu'un `aria-label` sur
    // un `div` nu n'est pas exposé.
    url.qs = `seasons=${CS},2023`;
    render(<SeasonTags seasons={SEASONS} />);

    expect(screen.getByRole("group", { name: "Saisons retenues" })).toBe(
      screen.getByTestId("season-tags"),
    );
  });

  it("laisse la page décider de l'alignement, qui dépend de son en-tête (revue UI/UX)", () => {
    // Le déclencheur passe à gauche quand l'en-tête s'empile, et chaque page
    // s'empile à sa propre largeur : un `justify-content` codé en dur ici
    // laissait les tags à droite pendant que le bouton, lui, était à gauche.
    url.qs = `seasons=${CS},2023`;
    render(<SeasonTags seasons={SEASONS} className="justify-start md:justify-end" />);

    const tags = screen.getByTestId("season-tags");
    expect(tags).toHaveClass("justify-start", "md:justify-end");
    expect(tags).toHaveClass("flex", "flex-wrap");
  });
});
