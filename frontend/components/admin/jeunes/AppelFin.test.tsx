import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect } from "vitest";
import type { EntrainementParticipant, Profile } from "@/lib/types";
import { AppelFin } from "./AppelFin";

const ALIX: Profile = {
  id: 42,
  organisation_id: 1,
  first_name: "Alix",
  last_name: "Martin",
  birth_date: null,
  created_at: "2026-01-01T00:00:00Z",
};

const ZOE: Profile = {
  id: 43,
  organisation_id: 1,
  first_name: "Zoé",
  last_name: "Roux",
  birth_date: null,
  created_at: "2026-01-01T00:00:00Z",
};

const PARTICIPANTS: EntrainementParticipant[] = [
  { jeune_id: 42, present: true, created_at: "2026-09-15T10:00:00Z" },
  { jeune_id: 43, present: false, created_at: "2026-09-15T10:00:00Z" },
];

describe("AppelFin", () => {
  it("ne montre que les jeunes marqués présents à l'appel de début", () => {
    render(<AppelFin participants={PARTICIPANTS} profils={[ALIX, ZOE]} />);

    expect(screen.getByText("Alix Martin")).toBeInTheDocument();
    expect(screen.queryByText("Zoé Roux")).not.toBeInTheDocument();
  });

  it("affiche un état vide explicite si personne n'a encore été pointé", () => {
    const participants: EntrainementParticipant[] = [
      { jeune_id: 42, present: null, created_at: "2026-09-15T10:00:00Z" },
    ];

    render(<AppelFin participants={participants} profils={[ALIX]} />);

    expect(screen.getByText(/rien à vérifier/i)).toBeInTheDocument();
  });

  it("coche un jeune sans écrire aucune donnée", async () => {
    render(<AppelFin participants={PARTICIPANTS} profils={[ALIX, ZOE]} />);

    expect(screen.getByText(/1 jeune restant/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("checkbox", { name: /alix martin/i }));

    expect(screen.getByText(/tous les jeunes présents/i)).toBeInTheDocument();
  });

  it("repart vierge après un remontage", async () => {
    const { unmount } = render(<AppelFin participants={PARTICIPANTS} profils={[ALIX, ZOE]} />);
    await userEvent.click(screen.getByRole("checkbox", { name: /alix martin/i }));
    expect(screen.getByText(/tous les jeunes présents/i)).toBeInTheDocument();
    unmount();

    render(<AppelFin participants={PARTICIPANTS} profils={[ALIX, ZOE]} />);

    expect(screen.getByText(/1 jeune restant/i)).toBeInTheDocument();
  });
});
