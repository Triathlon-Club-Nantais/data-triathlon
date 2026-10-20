import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { queryKeys } from "@/lib/queries/keys";
import type { AthleteBrief, ClaimedAthlete } from "@/lib/types";

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
import { currentSeason, seasonLabel } from "@/lib/utils/season";

const CIBLE: AthleteBrief = { id: 2, nom: "KERMARREC", prenom: "Hadrien", gender: "M", club: "TCN" };

function afficher(maFiche?: ClaimedAthlete) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
  if (maFiche) client.setQueryData(queryKeys.session(), { id: 1, permissions: [], athlete: maFiche });
  render(
    <QueryClientProvider client={client}>
      <VolunteerActionForm />
    </QueryClientProvider>,
  );
  return client;
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

  it("distingue une recherche en échec d'une recherche sans résultat, et l'annonce au lecteur d'écran", async () => {
    searchAthletesConnected.mockRejectedValue(new Error("réseau"));
    afficher();
    await userEvent.type(screen.getByLabelText(/athlète/i), "Ker");

    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/Recherche impossible/));
    expect(screen.queryByText(/Aucun athlète trouvé/)).not.toBeInTheDocument();
    expect(screen.getByLabelText(/athlète/i)).toHaveAttribute(
      "aria-describedby",
      screen.getByRole("alert").id,
    );
  });

  it("annonce la recherche en cours au lecteur d'écran (#608)", async () => {
    let resoudre: (value: AthleteBrief[]) => void;
    searchAthletesConnected.mockReturnValue(
      new Promise<AthleteBrief[]>((resolve) => (resoudre = resolve)),
    );
    afficher();
    await userEvent.type(screen.getByLabelText(/athlète/i), "Ker");

    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Recherche…"));

    resoudre!([CIBLE]);
    await waitFor(() => expect(screen.queryByRole("status")).not.toBeInTheDocument());
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
    expect(toastSuccess).toHaveBeenCalledWith(
      `Déclaration enregistrée pour Hadrien KERMARREC, ${seasonLabel(currentSeason()).toLowerCase()}, en attente de validation.`,
    );
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
    expect(screen.getByRole("button", { name: /changer d'athlète/i })).toBeDisabled();
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

  it("shows a French fallback, not the browser's raw message, on a network failure (#1045)", async () => {
    searchAthletesConnected.mockResolvedValue([CIBLE]);
    createVolunteerAction.mockRejectedValue(new TypeError("Failed to fetch"));

    afficher();
    await userEvent.type(screen.getByLabelText(/athlète/i), "Ker");
    await waitFor(() => expect(screen.getByText(/Hadrien KERMARREC/)).toBeInTheDocument());
    await userEvent.click(screen.getByText(/Hadrien KERMARREC/));
    await userEvent.type(screen.getByLabelText("Titre"), "T");
    await userEvent.type(screen.getByLabelText("Description"), "D");
    await userEvent.click(screen.getByRole("button", { name: /déclarer/i }));

    await waitFor(() =>
      expect(toastError).toHaveBeenCalledWith(
        "Enregistrement impossible pour le moment. Réessayez dans un instant.",
      ),
    );
  });

  describe("membre rattaché à sa fiche (#1672)", () => {
    const MOI: ClaimedAthlete = { id: 7, prenom: "Léa", nom: "Martin" };

    it("présélectionne sa fiche et la déclare sans recherche", async () => {
      createVolunteerAction.mockResolvedValue({ id: 1, season: 2026 });
      afficher(MOI);

      expect(await screen.findByText("Léa Martin")).toBeInTheDocument();
      await userEvent.type(screen.getByLabelText("Titre"), "Buvette");
      await userEvent.type(screen.getByLabelText("Description"), "Stand du club");
      await userEvent.click(screen.getByRole("button", { name: /déclarer/i }));

      await waitFor(() =>
        expect(createVolunteerAction).toHaveBeenCalledWith({ athlete_id: 7, title: "Buvette", description: "Stand du club" }),
      );
      expect(await screen.findByText("Léa Martin")).toBeInTheDocument();
    });

    it("laisse déclarer pour un autre athlète", async () => {
      searchAthletesConnected.mockResolvedValue([CIBLE]);
      afficher(MOI);
      await userEvent.click(await screen.findByRole("button", { name: /changer d'athlète/i }));
      await userEvent.type(screen.getByLabelText(/athlète/i), "Ker");
      await userEvent.click(await screen.findByText(/Hadrien KERMARREC/));

      expect(screen.getByText("Hadrien KERMARREC")).toBeInTheDocument();
      expect(screen.queryByText("Léa Martin")).not.toBeInTheDocument();
    });

    it("donne le focus à la recherche et propose de revenir à sa fiche", async () => {
      afficher(MOI);
      await userEvent.click(await screen.findByRole("button", { name: /changer d'athlète/i }));

      expect(screen.getByLabelText(/athlète/i)).toHaveFocus();
      await userEvent.click(screen.getByRole("button", { name: "Revenir à ma fiche" }));
      expect(screen.getByText("Léa Martin")).toBeInTheDocument();
    });

    it("revient à sa fiche après une déclaration pour un autre athlète", async () => {
      searchAthletesConnected.mockResolvedValue([CIBLE]);
      createVolunteerAction.mockResolvedValue({ id: 1, season: 2026 });
      afficher(MOI);
      await userEvent.click(await screen.findByRole("button", { name: /changer d'athlète/i }));
      await userEvent.type(screen.getByLabelText(/athlète/i), "Ker");
      await userEvent.click(await screen.findByText(/Hadrien KERMARREC/));
      await userEvent.type(screen.getByLabelText("Titre"), "Chrono");
      await userEvent.type(screen.getByLabelText("Description"), "Arrivée");
      await userEvent.click(screen.getByRole("button", { name: /déclarer/i }));

      await waitFor(() => expect(createVolunteerAction).toHaveBeenCalledWith(expect.objectContaining({ athlete_id: 2 })));
      expect(await screen.findByText("Léa Martin")).toBeInTheDocument();
      expect(toastSuccess).toHaveBeenCalledWith(expect.stringContaining("pour Hadrien KERMARREC,"));
    });

    it("présélectionne la fiche arrivée après le premier rendu", async () => {
      const client = afficher();
      await screen.findByLabelText(/athlète/i);

      act(() => {
        client.setQueryData(queryKeys.session(), { id: 1, permissions: [], athlete: MOI });
      });

      expect(await screen.findByText("Léa Martin")).toBeInTheDocument();
    });

    it("ne remplace pas une recherche commencée avant l'arrivée de la session", async () => {
      const client = afficher();
      await userEvent.type(screen.getByLabelText(/athlète/i), "Ke");

      await act(async () => {
        client.setQueryData(queryKeys.session(), { id: 1, permissions: [], athlete: MOI });
        await new Promise((r) => setTimeout(r, 0));
      });

      expect(screen.getByLabelText(/athlète/i)).toHaveValue("Ke");
      expect(screen.queryByText("Léa Martin")).not.toBeInTheDocument();
    });

    it("recharge la liste de mes déclarations après un envoi", async () => {
      createVolunteerAction.mockResolvedValue({ id: 1, season: 2026 });
      const client = afficher(MOI);
      const invalider = vi.spyOn(client, "invalidateQueries");
      await userEvent.type(await screen.findByLabelText("Titre"), "Buvette");
      await userEvent.type(screen.getByLabelText("Description"), "Stand");
      await userEvent.click(screen.getByRole("button", { name: /déclarer/i }));

      await waitFor(() =>
        expect(invalider).toHaveBeenCalledWith({ queryKey: queryKeys.myVolunteerDeclarations() }),
      );
    });
  });
});
