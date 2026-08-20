import { render } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import Loading from "./loading";

describe("AjouterPage — squelette de chargement (ETAT-2)", () => {
  it("esquisse le titre, le formulaire et le tableau des derniers résultats, dans PageShell", () => {
    const { container } = render(<Loading />);

    expect(container.querySelector(".mx-auto")).toBeInTheDocument();
    expect(container.querySelectorAll('[data-slot="skeleton"]').length).toBeGreaterThanOrEqual(4);
  });
});
