import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { SeasonSelector, SeasonTags, buildSeasonsHref } from "./SeasonSelector";
import { currentSeason, seasonLabel } from "@/lib/utils/season";
import type { Season } from "@/lib/types";

// Query string mutable : la mise en page des tags (#445) ne s'observe qu'avec
// plusieurs saisons sélectionnées, donc `?seasons=` doit pouvoir varier d'un
// test à l'autre.
const url = vi.hoisted(() => ({ qs: "" }));
const push = vi.hoisted(() => vi.fn());

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
  usePathname: () => "/mon-espace",
  useSearchParams: () => new URLSearchParams(url.qs),
}));

beforeEach(() => {
  url.qs = "";
  push.mockClear();
});

const CS = currentSeason();
const SEASONS: Season[] = [
  { start_year: CS, label: seasonLabel(CS), event_count: 0, participation_count: 0, is_current: true },
  { start_year: 2023, label: "Saison 2023 — 2024", event_count: 3, participation_count: 12, is_current: false },
];

describe("buildSeasonsHref", () => {
  it("omet le paramètre quand seule la saison en cours est sélectionnée", () => {
    // saison en cours par défaut → pas de ?seasons
    const href = buildSeasonsHref([currentSeason()], "", "/mon-espace");
    expect(href === "/mon-espace" || href === "/mon-espace?").toBe(true);
    expect(href).not.toContain("seasons=");
  });
  it("sérialise plusieurs saisons et préserve le scope", () => {
    const href = buildSeasonsHref([2025, 2023], "scope=club", "/mon-espace");
    expect(href).toContain("seasons=2025%2C2023");
    expect(href).toContain("scope=club");
  });
  it("respecte le pathname fourni (#274 — réutilisé hors /mon-espace)", () => {
    const href = buildSeasonsHref([2023], "", "/club/athletes");
    expect(href).toBe("/club/athletes?seasons=2023");
  });
  it("conserve sports et les autres paramètres, retire rank (#987)", () => {
    const href = buildSeasonsHref([2023], "sports=all&rank=category&name=dupont", "/mon-espace");
    const params = new URL(href, "http://x").searchParams;
    expect(params.get("sports")).toBe("all");
    expect(params.get("name")).toBe("dupont");
    expect(params.get("seasons")).toBe("2023");
    expect(params.has("rank")).toBe(false);
  });
  it("retire seasons au retour à la saison en cours, sans perdre sports (#987)", () => {
    const href = buildSeasonsHref([currentSeason()], "sports=all&seasons=2023", "/mon-espace");
    expect(href).toBe("/mon-espace?sports=all");
  });
});

describe("SeasonSelector", () => {
  it("affiche par défaut le libellé de la saison en cours", () => {
    render(<SeasonSelector seasons={SEASONS} />);
    expect(screen.getByText(new RegExp(`Saison ${currentSeason()}`))).toBeInTheDocument();
  });

  it("porte la variante Tailwind data-pending:opacity-70 dès le rendu initial", () => {
    // Le trajet vers /mon-espace traverse le serveur (issue #345) : l'élément
    // qui recevra `data-pending` pendant la transition doit déjà porter la
    // classe qui l'exploite, sans quoi l'attribut ne sert à rien (piège
    // relevé sur RankTypeToggle, qui ne portait qu'un `style` en ligne).
    render(<SeasonSelector seasons={SEASONS} />);
    expect(screen.getByLabelText(/choisir les saisons/i).className).toContain(
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
    fireEvent.click(screen.getByLabelText(/choisir les saisons/i));
    const list = screen.getByText("Saison 2023 — 2024").closest("[data-slot='popover-content']");
    expect(list).not.toBeNull();
    expect(list?.className).toContain("data-pending:opacity-70");
  });

  it("gives the trigger a 44px touch target under md, 28px above (#479, #1510)", () => {
    render(<SeasonSelector seasons={SEASONS} />);
    const declencheur = screen.getByRole("button", { name: /choisir les saisons/i });
    expect(declencheur).toHaveClass("tcn-cible-tactile");
    // An inline min-height would beat the class media query.
    expect(declencheur.style.minHeight).toBe("");
  });
});

describe("SeasonSelector — sélection exclusive par défaut (#694)", () => {
  it("choisir une saison passée remplace la sélection au lieu de l'ajouter à la saison en cours", () => {
    // Avant #694 : cocher 2023 sans mode comparaison envoyait
    // `?seasons=<CS>,2023` (union avec la saison en cours déjà cochée par
    // défaut), pas `?seasons=2023` seul.
    render(<SeasonSelector seasons={SEASONS} />);
    fireEvent.click(screen.getByLabelText(/choisir les saisons/i));
    fireEvent.click(screen.getByLabelText("Saison 2023 — 2024", { exact: false, selector: "input" }));

    expect(push).toHaveBeenCalledWith("/mon-espace?seasons=2023");
  });

  it("garde « Inclure les autres disciplines » en changeant de saison (#987)", () => {
    url.qs = "sports=all";
    render(<SeasonSelector seasons={SEASONS} />);
    fireEvent.click(screen.getByLabelText(/choisir les saisons/i));
    fireEvent.click(screen.getByLabelText("Saison 2023 — 2024", { exact: false, selector: "input" }));

    expect(push).toHaveBeenCalledWith("/mon-espace?sports=all&seasons=2023");
  });

  it("les saisons sont des boutons radio hors mode comparaison — un seul choix possible", () => {
    render(<SeasonSelector seasons={SEASONS} />);
    fireEvent.click(screen.getByLabelText(/choisir les saisons/i));

    for (const s of SEASONS) {
      expect(screen.getByLabelText(s.label, { exact: false, selector: "input" })).toHaveAttribute("type", "radio");
    }
  });

  it("le mode comparaison est désactivé par défaut quand une seule saison est sélectionnée", () => {
    render(<SeasonSelector seasons={SEASONS} />);
    fireEvent.click(screen.getByLabelText(/choisir les saisons/i));

    expect(screen.getByLabelText("Comparer plusieurs saisons")).not.toBeChecked();
  });

  it("activer le mode comparaison bascule les saisons en cases à cocher, additives", () => {
    render(<SeasonSelector seasons={SEASONS} />);
    fireEvent.click(screen.getByLabelText(/choisir les saisons/i));
    fireEvent.click(screen.getByLabelText("Comparer plusieurs saisons"));

    for (const s of SEASONS) {
      expect(screen.getByLabelText(s.label, { exact: false, selector: "input" })).toHaveAttribute("type", "checkbox");
    }

    fireEvent.click(screen.getByLabelText("Saison 2023 — 2024", { exact: false, selector: "input" }));
    expect(push).toHaveBeenCalledWith(`/mon-espace?seasons=${CS}%2C2023`);
  });

  it("le mode comparaison s'active automatiquement si l'URL porte déjà plusieurs saisons", () => {
    url.qs = `seasons=${CS},2023`;
    render(<SeasonSelector seasons={SEASONS} />);
    fireEvent.click(screen.getByLabelText(/choisir les saisons/i));

    expect(screen.getByLabelText("Comparer plusieurs saisons")).toBeChecked();
    expect(screen.getByLabelText(SEASONS[0].label, { exact: false, selector: "input" })).toHaveAttribute(
      "type",
      "checkbox",
    );
  });

  it("désactiver le mode comparaison réduit la sélection à sa première saison", () => {
    url.qs = `seasons=${CS},2023`;
    render(<SeasonSelector seasons={SEASONS} />);
    fireEvent.click(screen.getByLabelText(/choisir les saisons/i));
    fireEvent.click(screen.getByLabelText("Comparer plusieurs saisons"));

    // Première saison retenue = la saison en cours (URL `seasons=${CS},2023`) :
    // c'est aussi le défaut, donc `buildSeasonsHref` omet `?seasons=`.
    expect(push).toHaveBeenCalledWith("/mon-espace");
  });

  it("décocher la dernière saison en mode comparaison retombe sur la saison en cours (comportement assumé, hors #694)", () => {
    render(<SeasonSelector seasons={SEASONS} />);
    fireEvent.click(screen.getByLabelText(/choisir les saisons/i));
    fireEvent.click(screen.getByLabelText("Comparer plusieurs saisons"));
    // Seule saison cochée par défaut : la saison en cours.
    fireEvent.click(screen.getByLabelText(SEASONS[0].label, { exact: false, selector: "input" }));

    expect(push).toHaveBeenCalledWith("/mon-espace");
  });

  it("le mode comparaison se resynchronise sur l'URL lors d'une navigation sans démontage (retour navigateur)", () => {
    // Une navigation arrière/avant change l'URL sans démonter le composant,
    // contrairement à un premier rendu : `compare` doit suivre `seasons`
    // plutôt que de rester figé sur l'état d'avant la navigation.
    url.qs = `seasons=${CS},2023`;
    const { rerender } = render(<SeasonSelector seasons={SEASONS} />);
    fireEvent.click(screen.getByLabelText(/choisir les saisons/i));
    expect(screen.getByLabelText("Comparer plusieurs saisons")).toBeChecked();

    url.qs = "seasons=2023";
    rerender(<SeasonSelector seasons={SEASONS} />);

    expect(screen.getByLabelText("Comparer plusieurs saisons")).not.toBeChecked();
    expect(screen.getByLabelText(SEASONS[1].label, { exact: false, selector: "input" })).toHaveAttribute(
      "type",
      "radio",
    );
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
    expect(screen.getByLabelText(/choisir les saisons/i)).toHaveTextContent(
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
