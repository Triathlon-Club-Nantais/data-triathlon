import { render } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import Loading from "./loading";

describe("ResultatsPage — squelette de chargement (ETAT-2)", () => {
  it("esquisse l'en-tête, la barre de filtres et le tableau, dans PageShell", () => {
    // Avant #476, ce squelette n'était pas enveloppé dans `PageShell` : la
    // vraie page fait `PageShell > space-y-6 > (PageHeader, filtres, table)`,
    // et le contenu sautait d'une largeur à l'autre au remplacement.
    const { container } = render(<Loading />);

    expect(container.querySelector(".mx-auto")).toBeInTheDocument();
    expect(container.querySelectorAll('[data-slot="skeleton"]').length).toBeGreaterThanOrEqual(6);
  });
});
