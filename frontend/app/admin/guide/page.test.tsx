import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import GuideAdminPage from "./page";

describe("GuideAdminPage", () => {
  it("rend le sommaire et les 15 sections admin", () => {
    render(<GuideAdminPage />);
    expect(screen.getByRole("heading", { name: "Guide", level: 1 })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Sommaire du guide" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Épreuves" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Fournisseurs en attente" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Accès et mots de passe" })).toBeInTheDocument();
    // Les 15 sections, une par <h2>.
    expect(screen.getAllByRole("heading", { level: 2 })).toHaveLength(15);
  });
});
