import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Table } from "./blocks";

describe("Table des textes légaux (#333)", () => {
  it("fait de la première cellule de chaque ligne son en-tête", () => {
    render(<Table head={["Nom", "Durée"]} rows={[["tcn_session", "7 jours"]]} />);
    expect(screen.getByRole("columnheader", { name: "Durée" })).toHaveAttribute("scope", "col");
    expect(screen.getByRole("rowheader", { name: "tcn_session" })).toHaveAttribute("scope", "row");
    expect(screen.getByRole("cell", { name: "7 jours" })).toBeInTheDocument();
  });
});
