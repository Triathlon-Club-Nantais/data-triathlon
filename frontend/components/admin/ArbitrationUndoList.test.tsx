import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  listIgnoredIdentityPairs: vi.fn(),
  unignoreIdentityPair: vi.fn(),
  listConfirmedIdentityClubs: vi.fn(),
  unconfirmIdentityClub: vi.fn(),
  listIgnoredCourseDuplicates: vi.fn(),
  unignoreCourseDuplicate: vi.fn(),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: api };
});
vi.mock("sonner", () => ({ toast: { success: api.toastSuccess, error: api.toastError } }));

import { IdentityArbitrations, IgnoredCourseDuplicates } from "./ArbitrationUndoList";

function afficher(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

beforeEach(() => {
  vi.clearAllMocks();
  api.listIgnoredIdentityPairs.mockResolvedValue({
    pairs: [
      {
        id: 7,
        ignored_at: "2026-10-07T09:00:00",
        athletes: [
          { id: 1, nom: "DUPONT", prenom: "Jean" },
          { id: 2, nom: "JEAN", prenom: "Dupont" },
        ],
      },
    ],
  });
  api.listConfirmedIdentityClubs.mockResolvedValue({
    clubs: [
      {
        id: 3, athlete_id: 5, nom: "MARTIN", prenom: "Thomas",
        club_key: "vendometriathlon", confirmed_at: "2026-10-07T09:00:00",
      },
    ],
  });
  api.listIgnoredCourseDuplicates.mockResolvedValue({
    pairs: [
      {
        id: 9,
        ignored_at: "2026-10-07T09:00:00",
        courses: [
          { id: 38, name: "Mesquer", event_date: "2026-06-13" },
          { id: 39, name: "Mesquer relais", event_date: "2026-06-13" },
        ],
      },
    ],
  });
});

describe("IdentityArbitrations", () => {
  it("replie les deux listes par défaut et annonce leur taille", async () => {
    afficher(<IdentityArbitrations />);

    const paires = await screen.findByText("Paires écartées (1)");
    const clubs = await screen.findByText("Clubs confirmés (1)");
    expect(paires.closest("details")).not.toHaveAttribute("open");
    expect(clubs.closest("details")).not.toHaveAttribute("open");
  });

  it("annule la mise à l'écart d'une paire", async () => {
    api.unignoreIdentityPair.mockResolvedValue(undefined);
    afficher(<IdentityArbitrations />);
    await userEvent.click(await screen.findByText("Paires écartées (1)"));

    const ligne = screen.getByText(/DUPONT Jean et JEAN Dupont/).closest("li")!;
    await userEvent.click(within(ligne).getByRole("button", { name: /annuler/i }));

    expect(api.unignoreIdentityPair).toHaveBeenCalledWith(7);
    expect(api.toastSuccess).toHaveBeenCalled();
  });

  it("annule la confirmation d'un club", async () => {
    api.unconfirmIdentityClub.mockResolvedValue(undefined);
    afficher(<IdentityArbitrations />);
    await userEvent.click(await screen.findByText("Clubs confirmés (1)"));

    const ligne = screen.getByText(/MARTIN Thomas/).closest("li")!;
    expect(within(ligne).getByText(/vendometriathlon/)).toBeInTheDocument();
    await userEvent.click(within(ligne).getByRole("button", { name: /annuler/i }));

    expect(api.unconfirmIdentityClub).toHaveBeenCalledWith(3);
  });

  it("dit l'échec d'une annulation", async () => {
    api.unignoreIdentityPair.mockRejectedValue(new Error("Cette paire n'est pas écartée."));
    afficher(<IdentityArbitrations />);
    await userEvent.click(await screen.findByText("Paires écartées (1)"));

    await userEvent.click(screen.getAllByRole("button", { name: /annuler/i })[0]);

    expect(api.toastError).toHaveBeenCalledWith("Cette paire n'est pas écartée.");
  });
});

describe("IgnoredCourseDuplicates", () => {
  it("liste les paires d'épreuves écartées, repliées, et annule l'une", async () => {
    api.unignoreCourseDuplicate.mockResolvedValue(undefined);
    afficher(<IgnoredCourseDuplicates />);

    const resume = await screen.findByText("Paires écartées (1)");
    expect(resume.closest("details")).not.toHaveAttribute("open");
    await userEvent.click(resume);
    await userEvent.click(screen.getByRole("button", { name: /annuler/i }));

    expect(screen.getByText(/Mesquer \(n° 38\) et Mesquer relais \(n° 39\)/)).toBeInTheDocument();
    expect(api.unignoreCourseDuplicate).toHaveBeenCalledWith(9);
  });

  it("dit qu'aucune paire n'est écartée", async () => {
    api.listIgnoredCourseDuplicates.mockResolvedValue({ pairs: [] });
    afficher(<IgnoredCourseDuplicates />);

    await userEvent.click(await screen.findByText("Paires écartées (0)"));

    expect(screen.getByText(/aucune paire écartée/i)).toBeInTheDocument();
  });
});
