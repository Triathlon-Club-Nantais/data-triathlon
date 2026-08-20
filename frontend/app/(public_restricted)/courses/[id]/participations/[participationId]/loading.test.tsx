import { render } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import Loading from "./loading";

describe("ParticipationDetailPage — squelette de chargement (ETAT-2)", () => {
  it("esquisse les liens de retour, l'en-tête et les blocs empilés, dans PageShell", () => {
    const { container } = render(<Loading />);

    expect(container.querySelector(".mx-auto")).toBeInTheDocument();
    expect(container.querySelectorAll('[data-slot="skeleton"]').length).toBeGreaterThanOrEqual(6);
  });
});
