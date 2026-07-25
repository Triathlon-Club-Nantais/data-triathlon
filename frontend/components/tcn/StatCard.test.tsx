import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatCard } from "./StatCard";

describe("StatCard", () => {
  it("affiche la sous-ligne quand un hint est fourni", () => {
    render(<StatCard label="Meilleur ratio" value="Top 14%" hint="42e sur 300" />);

    expect(screen.getByText("Top 14%")).toBeInTheDocument();
    expect(screen.getByText("42e sur 300")).toBeInTheDocument();
  });

  it("n'affiche aucune sous-ligne sans hint", () => {
    render(<StatCard label="Top 10" value={3} />);

    expect(screen.queryByText("42e sur 300")).not.toBeInTheDocument();
  });
});
