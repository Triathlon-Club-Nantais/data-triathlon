import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import Loading from "./loading";

describe("ChallengePage, squelette de chargement (#1541)", () => {
  it("annonce le chargement et esquisse l'en-tête, la description et le tableau, dans PageShell", () => {
    const { container } = render(<Loading />);

    expect(screen.getByRole("status")).toHaveTextContent("Chargement du classement du challenge");
    expect(container.querySelector('[aria-busy="true"]')).toBeInTheDocument();
    expect(container.querySelector(".mx-auto")).toBeInTheDocument();
    expect(container.querySelectorAll('[data-slot="skeleton"]').length).toBeGreaterThanOrEqual(8);
  });
});
