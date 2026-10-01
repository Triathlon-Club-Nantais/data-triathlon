import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ExternalLink, Table } from "./blocks";

describe("Table des textes légaux (#333)", () => {
  it("fait de la première cellule de chaque ligne son en-tête", () => {
    render(<Table label="Cookies" head={["Nom", "Durée"]} rows={[["tcn_session", "7 jours"]]} />);
    expect(screen.getByRole("columnheader", { name: "Durée" })).toHaveAttribute("scope", "col");
    expect(screen.getByRole("rowheader", { name: "tcn_session" })).toHaveAttribute("scope", "row");
    expect(screen.getByRole("cell", { name: "7 jours" })).toBeInTheDocument();
  });

  it("rend sa zone de défilement atteignable au clavier (WCAG 2.1.1)", () => {
    render(<Table label="Cookies" head={["Nom", "Durée"]} rows={[["tcn_session", "7 jours"]]} />);
    expect(screen.getByRole("region", { name: "Cookies" })).toHaveAttribute("tabIndex", "0");
  });
});

describe("ExternalLink (#333)", () => {
  it("annonce l'ouverture dans un nouvel onglet", () => {
    render(<ExternalLink href="https://www.cnil.fr/fr/plaintes">cnil.fr/fr/plaintes</ExternalLink>);
    expect(screen.getByRole("link", { name: "cnil.fr/fr/plaintes, nouvel onglet" })).toHaveAttribute(
      "target",
      "_blank",
    );
  });
});
