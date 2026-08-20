import { render } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import Loading from "./loading";

describe("DashboardPage — squelette de chargement (ETAT-2)", () => {
  it("esquisse l'en-tête, la grille de tuiles et les deux cartes, dans PageShell", () => {
    const { container } = render(<Loading />);

    // `PageShell` (pas un `<div>` nu comme l'ancien `/resultats/loading.tsx`) :
    // sans lui, le squelette ne fait pas la même largeur que la vraie page et
    // le contenu saute au remplacement.
    expect(container.querySelector(".mx-auto")).toBeInTheDocument();
    expect(container.querySelectorAll('[data-slot="skeleton"]').length).toBeGreaterThanOrEqual(9);
  });
});
