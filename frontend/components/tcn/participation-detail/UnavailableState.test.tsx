import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { UnavailableState } from "./UnavailableState";

describe("UnavailableState", () => {
  it("dit qu'un relais est exclu par choix, pas faute de données (#1091)", () => {
    render(<UnavailableState isRelay />);

    expect(screen.getByText(/épreuve en relais/i)).toBeInTheDocument();
    expect(screen.queryByText(/intégralité des résultats/i)).not.toBeInTheDocument();
  });

  it("garde le message générique pour une épreuve non éligible", () => {
    render(<UnavailableState isRelay={false} />);

    expect(screen.getByText(/intégralité des résultats/i)).toBeInTheDocument();
  });

  it("dit qu'un résultat en attente attend sa validation (#1281)", () => {
    render(<UnavailableState isRelay={false} validation="pending" />);

    expect(screen.getByText(/comparaison en attente de validation/i)).toBeTruthy();
    expect(screen.queryByText(/intégralité des résultats/i)).not.toBeInTheDocument();
  });

  it("dit qu'un résultat non conforme n'entre pas au classement (#1281)", () => {
    render(<UnavailableState isRelay={false} validation="rejected" />);

    expect(screen.getByText(/signalé non conforme/i)).toBeInTheDocument();
  });
});
