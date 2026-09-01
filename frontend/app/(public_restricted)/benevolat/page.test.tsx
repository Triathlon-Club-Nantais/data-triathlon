import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import BenevolatPage from "./page";

vi.mock("@/components/benevolat/VolunteerActionForm", () => ({
  VolunteerActionForm: () => <div data-testid="volunteer-action-form" />,
}));

describe("BenevolatPage — une seule section depuis le retrait de l'auto-déclaration (#816)", () => {
  it("affiche le formulaire de crédit d'un athlète", () => {
    render(<BenevolatPage />);

    expect(screen.getByTestId("volunteer-action-form")).toBeInTheDocument();
  });

  it("n'invite plus à se connecter", () => {
    render(<BenevolatPage />);

    expect(screen.queryByRole("button", { name: /se connecter/i })).not.toBeInTheDocument();
  });
});
