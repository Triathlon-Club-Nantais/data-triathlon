import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import Loading from "./loading";

describe("DashboardPage — squelette de chargement (ETAT-2)", () => {
  it("esquisse l'en-tête, la rangée de chiffres et les deux colonnes, dans PageShell", () => {
    const { container } = render(<Loading />);

    // `PageShell` (pas un `<div>` nu) : sans lui, le squelette ne fait pas la
    // même largeur que la vraie page et le contenu saute au remplacement.
    expect(container.querySelector(".mx-auto")).toBeInTheDocument();
    expect(screen.getAllByTestId("squelette-chiffre")).toHaveLength(5);
    expect(screen.getByTestId("squelette-centre")).toBeInTheDocument();
    expect(screen.getByTestId("squelette-droite")).toBeInTheDocument();
  });
});
