import { render } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import Loading from "./loading";

describe("AthletePage — squelette de chargement (ETAT-2, #488)", () => {
  it("esquisse le retour, les pastilles, l'avatar, le nom, trois tuiles et le tableau, dans PageShell", () => {
    const { container } = render(<Loading />);

    expect(container.querySelector(".mx-auto")).toBeInTheDocument();
    // Trois tuiles, pas cinq : le squelette ne peut pas connaître le régime
    // avant que les données n'arrivent — trois est le majorant du cas
    // fréquent (47% des profils tombent en régime réduit ou vide).
    const grille = container.querySelector("div.grid");
    expect(grille).not.toBeNull();
    expect(grille?.querySelectorAll('[data-slot="skeleton"]').length).toBe(3);
    expect(container.querySelectorAll('[data-slot="skeleton"]').length).toBeGreaterThanOrEqual(8);
  });
});
