import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import type { Entrainement } from "@/lib/types";
import { EntrainementForm } from "./EntrainementForm";

const SEANCE: Entrainement = {
  id: 1,
  date: "2026-09-20",
  heure_debut: "18:00:00",
  lieu: "Base nautique",
  type_seance: "Natation",
  participant_count: 0,
};

describe("EntrainementForm", () => {
  it("soumet une date seule quand rien d'autre n'est renseigné", async () => {
    const soumettre = vi.fn();
    render(
      <EntrainementForm soumettre={soumettre} enCours={false} libelleSoumission="Créer" />,
    );

    await userEvent.type(screen.getByLabelText(/^date$/i), "2026-09-20");
    await userEvent.click(screen.getByRole("button", { name: /créer/i }));

    expect(soumettre).toHaveBeenCalledWith({
      date: "2026-09-20",
      heure_debut: null,
      lieu: null,
      type_seance: null,
    });
  });

  it("se sème avec un entraînement existant, prêt à être corrigé", () => {
    render(
      <EntrainementForm
        entrainement={SEANCE}
        soumettre={vi.fn()}
        enCours={false}
        libelleSoumission="Enregistrer"
      />,
    );

    expect(screen.getByLabelText(/^date$/i)).toHaveValue("2026-09-20");
    expect(screen.getByLabelText(/lieu/i)).toHaveValue("Base nautique");
    expect(screen.getByLabelText(/type de séance/i)).toHaveValue("Natation");
  });

  it("désactive la soumission sans date", () => {
    render(<EntrainementForm soumettre={vi.fn()} enCours={false} libelleSoumission="Créer" />);

    expect(screen.getByRole("button", { name: /créer/i })).toBeDisabled();
  });
});
