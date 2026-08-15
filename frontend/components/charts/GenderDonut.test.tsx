import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { GenderDonut } from "./GenderDonut";

describe("GenderDonut", () => {
  it("trace une tranche par genre quand le genre est renseigné", () => {
    const { container } = render(
      <GenderDonut malePct={63.7} femalePct={36.3} hasGender />,
    );
    expect(container.querySelectorAll("path").length).toBe(2);
  });

  it("donne une alternative textuelle à chaque tranche", () => {
    const { container } = render(
      <GenderDonut malePct={63.7} femalePct={36.3} hasGender />,
    );
    const labels = [...container.querySelectorAll("path")].map((p) =>
      p.getAttribute("aria-label"),
    );
    expect(labels.some((l) => l?.includes("Homme") && l?.includes("63,7"))).toBe(true);
    expect(labels.some((l) => l?.includes("Femme") && l?.includes("36,3"))).toBe(true);
  });

  it("affiche un cercle neutre, sans tranche, quand le genre est absent", () => {
    const { container } = render(
      <GenderDonut malePct={0} femalePct={0} hasGender={false} />,
    );
    expect(container.querySelectorAll("path").length).toBe(0);
    expect(container.querySelector("circle")).toBeTruthy();
  });

  it("affiche le pourcentage d'hommes arrondi au centre", () => {
    const { getByText } = render(
      <GenderDonut malePct={63.7} femalePct={36.3} hasGender />,
    );
    expect(getByText("64%")).toBeInTheDocument();
  });

  it("légende les deux tranches avec leur pourcentage exact", () => {
    const { getByText } = render(
      <GenderDonut malePct={63.7} femalePct={36.3} hasGender />,
    );
    expect(getByText("Homme")).toBeInTheDocument();
    expect(getByText("63,7%")).toBeInTheDocument();
    expect(getByText("Femme")).toBeInTheDocument();
    expect(getByText("36,3%")).toBeInTheDocument();
  });
});
