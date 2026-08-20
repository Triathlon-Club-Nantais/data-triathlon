import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { EmptyState } from "./empty-state";

describe("EmptyState", () => {
  it("s'enveloppe dans une Card par défaut", () => {
    const { container } = render(<EmptyState title="Rien à afficher" />);

    expect(container.querySelector('[data-slot="card"]')).toBeInTheDocument();
  });

  it("saute sa propre Card avec `bare`, pour s'insérer dans un conteneur déjà cadré", () => {
    // Les 9 emplacements d'ETAT-3 vivent déjà dans un `tcn/Card` : sans `bare`,
    // EmptyState imbriquerait sa propre Card (rayon et bordure différents)
    // dans celle de l'appelant.
    const { container } = render(<EmptyState bare title="Rien à afficher" />);

    expect(container.querySelector('[data-slot="card"]')).not.toBeInTheDocument();
    expect(screen.getByText("Rien à afficher")).toBeInTheDocument();
  });
});
