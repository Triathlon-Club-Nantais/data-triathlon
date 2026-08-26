import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { RappelPosition } from "./RappelPosition";

describe("RappelPosition", () => {
  it("ne rend rien de visible quand `visible` est faux", () => {
    render(<RappelPosition visible={false} epreuves={3} rang={41} hrefAncre="#athlete-1" />);
    expect(screen.queryByText(/du club/)).not.toBeInTheDocument();
  });

  it("affiche le rang et le nombre d'épreuves, en lien vers l'ancre donnée", () => {
    render(<RappelPosition visible epreuves={3} rang={41} hrefAncre="/club/athletes#athlete-1" />);
    const lien = screen.getByRole("link", { name: /Vous : 3 épreuves — 41ᵉ du club/ });
    expect(lien).toHaveAttribute("href", "/club/athletes#athlete-1");
  });

  it("accorde « épreuve » au singulier", () => {
    render(<RappelPosition visible epreuves={1} rang={41} hrefAncre="#athlete-1" />);
    expect(screen.getByRole("link", { name: /Vous : 1 épreuve — 41ᵉ du club/ })).toBeInTheDocument();
  });
});
