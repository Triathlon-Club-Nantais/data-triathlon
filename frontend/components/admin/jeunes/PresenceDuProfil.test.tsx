import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { PresenceDuProfil } from "./PresenceDuProfil";

function afficher(attended: number, pointed: number, absence_streak: number) {
  return render(<PresenceDuProfil attendance={{ attended, pointed, absence_streak }} />);
}

describe("PresenceDuProfil (#1364)", () => {
  it("shows the rate and a single missed session", () => {
    afficher(1, 2, 1);
    // le normaliseur par défaut replie l'espace insécable fine : on le désactive pour la vérifier
    const brut = { normalizer: (texte: string) => texte };
    expect(screen.getByText("Assiduité : 50\u202f% (1 séance sur 2)", brut)).toBeInTheDocument();
    expect(screen.getByText("Dernière séance manquée.")).toBeInTheDocument();
  });

  it("says no roll call happened, without any percentage", () => {
    const { container } = afficher(0, 0, 0);
    expect(screen.getByText("Aucun appel cette saison.")).toBeInTheDocument();
    expect(container.textContent).not.toContain("%");
  });

  it("counts a streak of missed sessions", () => {
    afficher(1, 4, 3);
    expect(screen.getByText("3 séances manquées d'affilée.")).toBeInTheDocument();
  });

  it("shows no missed line at a zero streak", () => {
    afficher(4, 4, 0);
    expect(screen.queryByText(/manquée/)).toBeNull();
  });
});
