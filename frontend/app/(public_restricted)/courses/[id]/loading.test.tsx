import { render } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import Loading from "./loading";

describe("CoursePage — squelette de chargement (ETAT-2)", () => {
  it("esquisse l'en-tête, les trois cartes de synthèse et le tableau, dans PageShell", () => {
    const { container } = render(<Loading />);

    expect(container.querySelector(".mx-auto")).toBeInTheDocument();
    expect(container.querySelectorAll('[data-slot="skeleton"]').length).toBeGreaterThanOrEqual(9);
  });
});
