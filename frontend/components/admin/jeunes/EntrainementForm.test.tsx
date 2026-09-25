import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import type { TrainingSession } from "@/lib/types";
import { EntrainementForm } from "./EntrainementForm";

const SEANCE: TrainingSession = {
  id: 1,
  date: "2026-09-20",
  start_time: "18:00:00",
  location: "Base nautique",
  session_type: "Natation",
  note: "",
  participant_count: 0,
};

describe("EntrainementForm", () => {
  it("garde ses libellés quand un second formulaire est à l'écran", () => {
    render(
      <>
        <EntrainementForm soumettre={vi.fn()} enCours={false} libelleSoumission="Créer" />
        <EntrainementForm
          entrainement={SEANCE}
          soumettre={vi.fn()}
          enCours={false}
          libelleSoumission="Enregistrer"
        />
      </>,
    );

    const lieux = screen.getAllByLabelText(/^lieu$/i);
    expect(lieux).toHaveLength(2);
    expect(lieux[1]).toHaveValue("Base nautique");
  });

  it("soumet une date seule quand rien d'autre n'est renseigné", async () => {
    const soumettre = vi.fn();
    render(
      <EntrainementForm soumettre={soumettre} enCours={false} libelleSoumission="Créer" />,
    );

    await userEvent.type(screen.getByLabelText(/^date$/i), "2026-09-20");
    await userEvent.click(screen.getByRole("button", { name: /créer/i }));

    expect(soumettre).toHaveBeenCalledWith({
      date: "2026-09-20",
      start_time: null,
      location: null,
      session_type: null,
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
