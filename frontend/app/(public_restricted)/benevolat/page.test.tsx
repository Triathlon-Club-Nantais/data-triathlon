import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import BenevolatPage from "./page";

vi.mock("@/components/benevolat/VolunteerActionForm", () => ({
  VolunteerActionForm: () => <div data-testid="volunteer-action-form" />,
}));
vi.mock("@/components/benevolat/MesDeclarations", () => ({
  MesDeclarations: () => <div data-testid="mes-declarations" />,
}));

describe("BenevolatPage — une seule section depuis le retrait de l'auto-déclaration (#816)", () => {
  it("affiche le formulaire de crédit d'un athlète", () => {
    render(<BenevolatPage />);

    expect(screen.getByTestId("volunteer-action-form")).toBeInTheDocument();
  });

  it("affiche mes déclarations sous le formulaire (#1672)", () => {
    render(<BenevolatPage />);

    const formulaire = screen.getByTestId("volunteer-action-form");
    expect(formulaire.compareDocumentPosition(screen.getByTestId("mes-declarations"))).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    );
  });

  it("n'invite plus à se connecter", () => {
    render(<BenevolatPage />);

    expect(screen.queryByRole("button", { name: /se connecter/i })).not.toBeInTheDocument();
  });
});
