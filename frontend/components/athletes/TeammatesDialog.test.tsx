import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api/client";
import type { AdminAthlete, AthleteBrief } from "@/lib/types";
import { TeammatesDialog } from "./TeammatesDialog";

const { searchAthletesAdmin, setParticipationTeammates } = vi.hoisted(() => ({
  searchAthletesAdmin: vi.fn(),
  setParticipationTeammates: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { searchAthletesAdmin, setParticipationTeammates } };
});

const { toastSuccess, toastError } = vi.hoisted(() => ({
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}));
vi.mock("sonner", () => ({ toast: { success: toastSuccess, error: toastError } }));

const { refresh } = vi.hoisted(() => ({ refresh: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh }) }));

function fiche(id: number, nom: string, prenom: string): AdminAthlete {
  return { id, nom, prenom, birth_date: null, gender: "M", club: "TCN", participations: 1 };
}

const JEAN = fiche(10, "DUPONT", "Jean");
const PAUL = fiche(11, "MARTIN", "Paul");

const RESULTAT = { id: 314, epreuve: "Relais de Nantes", date: "2026-06-01" };

function afficher(equipiers: AthleteBrief[] = [], onClose = vi.fn()) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <TeammatesDialog resultat={RESULTAT} equipiers={equipiers} onClose={onClose} />
    </QueryClientProvider>,
  );
  return onClose;
}

async function ajouter(athlete: AdminAthlete) {
  searchAthletesAdmin.mockResolvedValue([athlete]);
  const champ = screen.getByRole("searchbox");
  await userEvent.clear(champ);
  await userEvent.type(champ, athlete.nom);
  await userEvent.click(
    await screen.findByRole("button", { name: `Ajouter ${athlete.nom} ${athlete.prenom}` }),
  );
}

describe("TeammatesDialog", () => {
  beforeEach(() => {
    searchAthletesAdmin.mockReset();
    setParticipationTeammates.mockReset();
    toastSuccess.mockReset();
    toastError.mockReset();
    refresh.mockReset();
  });

  it("n'attribue rien tant que l'équipe compte moins de deux coureurs", async () => {
    afficher();

    expect(screen.getByRole("button", { name: "Attribuer" })).toBeDisabled();
    await ajouter(JEAN);
    expect(screen.getByRole("button", { name: "Attribuer" })).toBeDisabled();
  });

  it("renvoie vers le rattachement quand il ne reste qu'un coureur", async () => {
    afficher();

    await ajouter(JEAN);

    expect(screen.getByRole("status")).toHaveTextContent(
      "Pour un seul coureur, utilisez « Rattacher ».",
    );
  });

  it("attribue le relais aux coureurs choisis, dans l'ordre", async () => {
    setParticipationTeammates.mockResolvedValue({});
    const onClose = afficher();

    await ajouter(JEAN);
    await ajouter(PAUL);
    await userEvent.click(screen.getByRole("button", { name: "Attribuer" }));

    await waitFor(() => expect(setParticipationTeammates).toHaveBeenCalledWith(314, [10, 11]));
    expect(toastSuccess).toHaveBeenCalledWith("Relais attribué à 2 coureurs.");
    expect(refresh).toHaveBeenCalled();
    expect(onClose).toHaveBeenCalled();
  });

  it("part de la composition actuelle et permet d'en retirer un coureur", async () => {
    setParticipationTeammates.mockResolvedValue({});
    afficher([JEAN, PAUL]);
    const marie = fiche(12, "DURAND", "Marie");

    await userEvent.click(screen.getByRole("button", { name: "Retirer MARTIN Paul" }));
    await ajouter(marie);
    await userEvent.click(screen.getByRole("button", { name: "Attribuer" }));

    await waitFor(() => expect(setParticipationTeammates).toHaveBeenCalledWith(314, [10, 12]));
  });

  it("ne propose pas un coureur déjà dans l'équipe", async () => {
    searchAthletesAdmin.mockResolvedValue([JEAN, PAUL]);
    afficher([JEAN]);

    await userEvent.type(screen.getByRole("searchbox"), "d");

    expect(await screen.findByRole("button", { name: "Ajouter MARTIN Paul" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Ajouter DUPONT Jean" })).not.toBeInTheDocument();
  });

  it("ajoute un coureur sans fiche par son nom et son prénom", async () => {
    setParticipationTeammates.mockResolvedValue({});
    afficher([JEAN]);

    const ajouterLaPersonne = screen.getByRole("button", { name: "Ajouter cette personne" });
    expect(ajouterLaPersonne).toBeDisabled();
    await userEvent.type(screen.getByLabelText("Nom"), "DURAND");
    expect(ajouterLaPersonne).toBeDisabled();
    await userEvent.type(screen.getByLabelText("Prénom"), "Marie");
    await userEvent.click(ajouterLaPersonne);
    await userEvent.click(screen.getByRole("button", { name: "Attribuer" }));

    await waitFor(() =>
      expect(setParticipationTeammates).toHaveBeenCalledWith(314, [
        10,
        { athlete_name: "DURAND", athlete_firstname: "Marie" },
      ]),
    );
  });

  it("affiche le refus du serveur à côté de la liste", async () => {
    setParticipationTeammates.mockRejectedValue(
      new ApiError(409, "MARTIN Paul a déjà un résultat sur cette épreuve."),
    );
    const onClose = afficher([JEAN, PAUL]);

    await userEvent.click(screen.getByRole("button", { name: "Attribuer" }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      "MARTIN Paul a déjà un résultat sur cette épreuve.",
    );
    expect(onClose).not.toHaveBeenCalled();
  });
});
