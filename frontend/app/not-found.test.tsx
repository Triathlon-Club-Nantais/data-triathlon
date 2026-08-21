import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";

import NotFound from "./not-found";

describe("app/not-found", () => {
  it("nomme ce qui manque en français, dans un titre de page (A11Y-2, #464)", () => {
    render(<NotFound />);

    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      /n'existe pas/i,
    );
  });

  it("dit qu'un lien partagé vers une épreuve disparue mène ici", () => {
    render(<NotFound />);

    expect(screen.getByText(/fusionnée ou supprimée/i)).toBeInTheDocument();
  });

  it("propose trois sorties au lieu d'un cul-de-sac (#464, ETAT-1)", () => {
    render(<NotFound />);

    expect(screen.getByRole("link", { name: /résultats/i })).toHaveAttribute(
      "href",
      "/resultats",
    );
    expect(screen.getByRole("link", { name: /ajouter une épreuve/i })).toHaveAttribute(
      "href",
      "/ajouter",
    );
    expect(screen.getByRole("link", { name: /tableau de bord/i })).toHaveAttribute(
      "href",
      "/dashboard",
    );
  });

  it("ne renvoie pas vers la carte, que le rail masque volontairement (#10, #28)", () => {
    render(<NotFound />);

    // Sur le `href`, pas sur le libellé : « Explorer les épreuves » vers
    // `/carte` rouvrirait l'écran masqué sans que le mot « carte » apparaisse.
    const destinations = screen.getAllByRole("link").map((lien) => lien.getAttribute("href"));
    expect(destinations).not.toContain("/carte");
  });
});
