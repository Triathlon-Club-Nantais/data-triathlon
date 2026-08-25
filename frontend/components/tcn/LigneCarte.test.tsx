// frontend/components/tcn/LigneCarte.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LigneCarte } from "./LigneCarte";

describe("LigneCarte", () => {
  it("rend une ancre quand la carte mène quelque part", () => {
    render(<LigneCarte href="/courses/1" titre="Triathlon de Nantes" />);
    expect(screen.getByRole("link", { name: /Triathlon de Nantes/ })).toHaveAttribute(
      "href",
      "/courses/1",
    );
  });

  it("rend un bouton nommé quand la carte agit au lieu de naviguer", async () => {
    const onSelect = vi.fn();
    render(
      <LigneCarte onSelect={onSelect} ariaLabel="Déplier Coupe de Bretagne" ouvert={false} titre="Coupe de Bretagne" />,
    );
    const bouton = screen.getByRole("button", { name: "Déplier Coupe de Bretagne" });
    expect(bouton).toHaveAttribute("aria-expanded", "false");
    await userEvent.click(bouton);
    expect(onSelect).toHaveBeenCalledTimes(1);
  });

  it("rend surtitre, marqueur, valeur et méta", () => {
    render(
      <LigneCarte
        href="/x"
        surtitre="12 mai 2025"
        marqueur={<span>①</span>}
        titre="Jean DUPONT"
        valeur="1:04:12"
        meta="TCN · SEM · H"
      />,
    );
    expect(screen.getByText("12 mai 2025")).toBeInTheDocument();
    expect(screen.getByText("①")).toBeInTheDocument();
    expect(screen.getByText("1:04:12")).toBeInTheDocument();
    expect(screen.getByText("TCN · SEM · H")).toBeInTheDocument();
  });

  // Un <button> ou un <a> imbriqué dans un <a> est du HTML invalide : le
  // dépliant et les actions doivent rester FRÈRES de la zone cliquable.
  it("garde le dépliant hors de la zone cliquable", () => {
    render(
      <LigneCarte
        href="/x"
        titre="Jean DUPONT"
        depliant={{ libelle: "Inters", contenu: <span>12:03</span> }}
      />,
    );
    const lien = screen.getByRole("link", { name: /Jean DUPONT/ });
    const resume = screen.getByText("Inters");
    expect(lien).not.toContainElement(resume);
  });

  it("garde les actions hors de la zone cliquable", () => {
    render(
      <LigneCarte href="/x" titre="Jean DUPONT" actions={<a href="/preuve">Voir la preuve</a>} />,
    );
    const lien = screen.getByRole("link", { name: /Jean DUPONT/ });
    expect(lien).not.toContainElement(screen.getByRole("link", { name: "Voir la preuve" }));
  });

  // WCAG 2.2 2.5.8 : 24 px est le minimum normatif, 44 px le seuil au doigt
  // que la coquille de l'app se donne déjà (AppNav).
  it("donne 44 px de haut à la zone cliquable et au résumé du dépliant", () => {
    render(
      <LigneCarte
        href="/x"
        titre="Jean DUPONT"
        depliant={{ libelle: "Inters", contenu: <span>12:03</span> }}
      />,
    );
    expect(screen.getByRole("link", { name: /Jean DUPONT/ })).toHaveStyle({ minHeight: "44px" });
    expect(screen.getByText("Inters").closest("summary")).toHaveStyle({ minHeight: "44px" });
  });

  // `toHaveStyle` ne voit PAS un `var()` posé dans un raccourci sous jsdom :
  // cssstyle abandonne la déclaration au calcul, et l'assertion échoue sur du
  // code correct (vérifié à l'exécution). L'attribut `style`, lui, la porte
  // telle quelle — c'est donc lui qu'on lit. `toHaveStyle` reste bon pour les
  // valeurs sans variable, comme le `minHeight` du test précédent.
  it("pose le liseré orange sur une ligne du club et le retire sinon", () => {
    const { rerender } = render(<LigneCarte href="/x" titre="Jean DUPONT" accent />);
    expect(screen.getByRole("article").getAttribute("style")).toContain(
      "border-left: 3px solid var(--tcn-orange)",
    );

    rerender(<LigneCarte href="/x" titre="Jean DUPONT" />);
    expect(screen.getByRole("article").getAttribute("style")).toContain(
      "border-left: 3px solid transparent",
    );
  });

  // Même piège cssstyle que le liseré : `color-mix(...)` contient une
  // variable, `toHaveStyle` ne la voit pas sous jsdom. On lit l'attribut.
  it("pose le fond atténué pour un non-finisher", () => {
    render(<LigneCarte href="/x" titre="Jean DUPONT" attenue />);
    expect(screen.getByRole("article").getAttribute("style")).toContain(
      "color-mix(in srgb, var(--tcn-grey-400) 15%, transparent)",
    );
  });

  // Vérifications de type seules : vitest transpile les .test.tsx avec esbuild
  // sans type-checker, donc ces deux cas ne rougissent qu'à `npm run build`
  // (tsc strict). `it.skip` : jamais exécutées, seulement compilées — un
  // `@ts-expect-error` sur du code que TS accepte est lui-même une erreur, ce
  // qui rend le test auto-vérifiant.
  it.skip("le type refuse une carte sans zone cliquable", () => {
    // @ts-expect-error — ni `href` ni `onSelect` : union Navigation | Action non satisfaite.
    return <LigneCarte titre="x" />;
  });

  it.skip("le type refuse onSelect sans ariaLabel", () => {
    // @ts-expect-error — `ariaLabel` est requis avec `onSelect` : le bouton perdrait son nom accessible.
    return <LigneCarte onSelect={() => {}} titre="x" />;
  });
});
