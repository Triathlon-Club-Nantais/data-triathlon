import { render } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import Loading from "./loading";

describe("AthletePage — squelette de chargement (ETAT-2)", () => {
  it("esquisse l'avatar, le nom, les cinq tuiles et le tableau, dans PageShell", () => {
    const { container } = render(<Loading />);

    expect(container.querySelector(".mx-auto")).toBeInTheDocument();
    expect(container.querySelectorAll('[data-slot="skeleton"]').length).toBeGreaterThanOrEqual(8);
  });
});
