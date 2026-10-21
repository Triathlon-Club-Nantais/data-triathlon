import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { PageHeader } from "./PageHeader";

// Revue UI/UX de fin de branche #488 : le slot `actions` débordait à 360px
// (WCAG 1.4.10, `.tcn-btn` est `white-space: nowrap`) et désalignait deux
// commandes de hauteur différente. On assert la classe porteuse plutôt
// qu'une mesure au pixel — un test unitaire ne peut pas prouver le rendu.
describe("PageHeader — slot actions", () => {
  it("porte flex-wrap et items-start sur son conteneur d'actions", () => {
    render(
      <PageHeader
        title="Titre"
        actions={<button type="button">Une action</button>}
      />,
    );

    const action = screen.getByRole("button", { name: "Une action" });
    const conteneur = action.parentElement;
    expect(conteneur).not.toBeNull();
    expect(conteneur?.className).toContain("flex-wrap");
    expect(conteneur?.className).toContain("items-start");
    expect(conteneur?.className).not.toContain("items-center");
  });

  it("laisse le groupe d'actions rétrécir à côté du titre (#1011)", () => {
    // `shrink-0` gardait « Corriger la fiche » et « Choisir cet athlète » (300 px
    // de texte d'aide) sur une ligne : la fiche athlète débordait de 640 à 768 px.
    render(<PageHeader title="Titre" actions={<button type="button">Une action</button>} />);

    const conteneur = screen.getByRole("button", { name: "Une action" }).parentElement;
    expect(conteneur?.className).not.toContain("shrink-0");
    expect(conteneur?.className).toContain("min-w-0");
  });
});

describe("PageHeader: row layout follows its own width (#1774)", () => {
  it("switches to a row on a container query, not on the viewport", () => {
    // With the 288 px sidebar (#1336), `sm:` left ~450 px to the header at
    // 800 px: the nowrap merge button overflowed by 31 px.
    const { container } = render(<PageHeader title="Titre" actions={<button type="button">Une action</button>} />);
    const rangee = screen.getByRole("heading", { name: "Titre" }).parentElement?.parentElement;

    expect(container.firstElementChild).toHaveClass("@container");
    expect(rangee?.className).toContain("@xl:flex-row");
    expect(rangee?.className).not.toContain("sm:flex-row");
  });
});

describe("PageHeader: help link (#1245)", () => {
  it("links to the guide section when `helpHref` is given, with a 44 px target", () => {
    render(<PageHeader title="Titre" helpHref="/admin/guide#identites" />);
    const link = screen.getByRole("link", { name: "Aide" });
    expect(link).toHaveAttribute("href", "/admin/guide#identites");
    expect(link).toHaveClass("min-h-11");
  });

  it("renders no help link without `helpHref`", () => {
    render(<PageHeader title="Titre" />);
    expect(screen.queryByRole("link", { name: "Aide" })).toBeNull();
  });
});
