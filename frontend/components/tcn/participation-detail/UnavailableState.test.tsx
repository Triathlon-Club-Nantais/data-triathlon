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
});
