import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatCard } from "./StatCard";

describe("StatCard", () => {
  it("affiche le delta sur la variante standard", () => {
    render(<StatCard label="Podiums" value={22} delta="scratch, genre ou catégorie" />);
    expect(screen.getByText("scratch, genre ou catégorie")).toBeInTheDocument();
  });

  it("affiche le delta sur la variante hero", () => {
    render(<StatCard variant="hero" label="Dossards" value={120} delta="12 athlètes" />);
    expect(screen.getByText("12 athlètes")).toBeInTheDocument();
  });
});
