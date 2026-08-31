import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { AthleteBrief } from "@/lib/types";

const { searchAthletesConnected, createVolunteerAction } = vi.hoisted(() => ({
  searchAthletesConnected: vi.fn(),
  createVolunteerAction: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { ...original.apiClient, searchAthletesConnected, createVolunteerAction } };
});

const { toastSuccess, toastError } = vi.hoisted(() => ({
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}));
vi.mock("sonner", () => ({ toast: { success: toastSuccess, error: toastError } }));

import { VolunteerActionForm } from "./VolunteerActionForm";

const CIBLE: AthleteBrief = { id: 2, nom: "KERMARREC", prenom: "Hadrien", gender: "M", club: "TCN" };

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <VolunteerActionForm />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("VolunteerActionForm", () => {
  it("ne recherche pas sous 2 caractères", async () => {
    afficher();
    await userEvent.type(screen.getByLabelText(/athlète/i), "K");

    await new Promise((r) => setTimeout(r, 350));
    expect(searchAthletesConnected).not.toHaveBeenCalled();
  });

  it("recherche à partir de 2 caractères", async () => {
    searchAthletesConnected.mockResolvedValue([CIBLE]);
    afficher();
    await userEvent.type(screen.getByLabelText(/athlète/i), "Ke");

    await waitFor(() => expect(searchAthletesConnected).toHaveBeenCalledWith("Ke"));
  });

  it("affiche un état vide quand la recherche ne trouve personne", async () => {
    searchAthletesConnected.mockResolvedValue([]);
    afficher();
    await userEvent.type(screen.getByLabelText(/athlète/i), "Zzz");

    await waitFor(() => expect(screen.getByText(/Aucun athlète trouvé/)).toBeInTheDocument());
  });

  it("distingue une recherche en échec d'une recherche sans résultat", async () => {
    searchAthletesConnected.mockRejectedValue(new Error("réseau"));
    afficher();
    await userEvent.type(screen.getByLabelText(/athlète/i), "Ker");

    await waitFor(() =>
      expect(screen.getByText(/Recherche impossible pour le moment/)).toBeInTheDocument(),
    );
    expect(screen.queryByText(/Aucun athlète trouvé/)).not.toBeInTheDocument();
  });

  it("les résultats n'affichent que nom/prénom/club, jamais de date de naissance", async () => {
    searchAthletesConnected.mockResolvedValue([CIBLE]);
    afficher();
    await userEvent.type(screen.getByLabelText(/athlète/i), "Ker");

    await waitFor(() => expect(screen.getByText(/Hadrien KERMARREC/)).toBeInTheDocument());
    expect(screen.queryByText(/birth_date/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/\d{4}-\d{2}-\d{2}/)).not.toBeInTheDocument();
  });

  it("sélectionne un athlète depuis les résultats", async () => {
    searchAthletesConnected.mockResolvedValue([CIBLE]);
    afficher();
    await userEvent.type(screen.getByLabelText(/athlète/i), "Ker");
    await waitFor(() => expect(screen.getByText(/Hadrien KERMARREC/)).toBeInTheDocument());
    await userEvent.click(screen.getByText(/Hadrien KERMARREC/));

    expect(screen.getByText(/Hadrien KERMARREC/)).toBeInTheDocument();
    expect(screen.queryByLabelText(/athlète/i)).not.toBeInTheDocument();
  });

  it("refuse la soumission sans athlète sélectionné", async () => {
    afficher();
    await userEvent.type(screen.getByLabelText("Titre"), "Ravitaillement");
    await userEvent.type(screen.getByLabelText("Description"), "Poste eau");
    await userEvent.click(screen.getByRole("button", { name: /déclarer/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/athlète/i);
    expect(createVolunteerAction).not.toHaveBeenCalled();
  });

  it("refuse la soumission quand le titre ou la description est vide", async () => {
    searchAthletesConnected.mockResolvedValue([CIBLE]);
    afficher();
    await userEvent.type(screen.getByLabelText(/athlète/i), "Ker");
    await waitFor(() => expect(screen.getByText(/Hadrien KERMARREC/)).toBeInTheDocument());
    await userEvent.click(screen.getByText(/Hadrien KERMARREC/));
    await userEvent.click(screen.getByRole("button", { name: /déclarer/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/obligatoires/i);
    expect(createVolunteerAction).not.toHaveBeenCalled();
  });

  it("soumet athlète, titre et description au clic", async () => {
    searchAthletesConnected.mockResolvedValue([CIBLE]);
    createVolunteerAction.mockResolvedValue({
      id: 1,
      athlete_id: 2,
      season: 2026,
      title: "Ravitaillement",
      description: "Poste eau",
      status: "en_attente",
      declared_by_user_id: 1,
      created_at: "2026-08-31T16:00:00Z",
    });

    afficher();
    await userEvent.type(screen.getByLabelText(/athlète/i), "Ker");
    await waitFor(() => expect(screen.getByText(/Hadrien KERMARREC/)).toBeInTheDocument());
    await userEvent.click(screen.getByText(/Hadrien KERMARREC/));
    await userEvent.type(screen.getByLabelText("Titre"), "Ravitaillement");
    await userEvent.type(screen.getByLabelText("Description"), "Poste eau");
    await userEvent.click(screen.getByRole("button", { name: /déclarer/i }));

    await waitFor(() =>
      expect(createVolunteerAction).toHaveBeenCalledWith({
        athlete_id: 2,
        title: "Ravitaillement",
        description: "Poste eau",
      }),
    );
    expect(toastSuccess).toHaveBeenCalled();
  });

  it("désactive le bouton pendant la requête", async () => {
    searchAthletesConnected.mockResolvedValue([CIBLE]);
    let resoudre: (value: unknown) => void;
    createVolunteerAction.mockReturnValue(new Promise((resolve) => (resoudre = resolve)));

    afficher();
    await userEvent.type(screen.getByLabelText(/athlète/i), "Ker");
    await waitFor(() => expect(screen.getByText(/Hadrien KERMARREC/)).toBeInTheDocument());
    await userEvent.click(screen.getByText(/Hadrien KERMARREC/));
    await userEvent.type(screen.getByLabelText("Titre"), "T");
    await userEvent.type(screen.getByLabelText("Description"), "D");
    await userEvent.click(screen.getByRole("button", { name: /déclarer/i }));

    expect(screen.getByRole("button", { name: /déclarer/i })).toBeDisabled();
    resoudre!({
      id: 1,
      athlete_id: 2,
      season: 2026,
      title: "T",
      description: "D",
      status: "en_attente",
      declared_by_user_id: 1,
      created_at: "2026-08-31T16:00:00Z",
    });
    await waitFor(() => expect(toastSuccess).toHaveBeenCalled());
  });

  it("affiche un message d'échec si la création échoue", async () => {
    searchAthletesConnected.mockResolvedValue([CIBLE]);
    createVolunteerAction.mockRejectedValue(new Error("Boum"));

    afficher();
    await userEvent.type(screen.getByLabelText(/athlète/i), "Ker");
    await waitFor(() => expect(screen.getByText(/Hadrien KERMARREC/)).toBeInTheDocument());
    await userEvent.click(screen.getByText(/Hadrien KERMARREC/));
    await userEvent.type(screen.getByLabelText("Titre"), "T");
    await userEvent.type(screen.getByLabelText("Description"), "D");
    await userEvent.click(screen.getByRole("button", { name: /déclarer/i }));

    await waitFor(() => expect(toastError).toHaveBeenCalled());
  });
});
