import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { AdminVolunteerActionOut } from "@/lib/types";
import { DangerConfirmProvider } from "@/components/admin/DangerConfirm";
import { confirmerDansLeDialog } from "@/components/admin/__tests__/dangerConfirm";
import { AdminVolunteerActionsTable } from "./AdminVolunteerActionsTable";
import { seasonLabel } from "@/lib/utils/season";
import { formatDate } from "@/lib/utils/date";

const {
  listPendingVolunteerActions,
  acceptVolunteerAction,
  rejectVolunteerAction,
  deleteVolunteerAction,
} = vi.hoisted(() => ({
  listPendingVolunteerActions: vi.fn(),
  acceptVolunteerAction: vi.fn(),
  rejectVolunteerAction: vi.fn(),
  deleteVolunteerAction: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: {
      ...original.apiClient,
      listPendingVolunteerActions,
      acceptVolunteerAction,
      rejectVolunteerAction,
      deleteVolunteerAction,
    },
  };
});

const { toastSuccess, toastError } = vi.hoisted(() => ({
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}));
vi.mock("sonner", () => ({ toast: { success: toastSuccess, error: toastError } }));

const EN_ATTENTE: AdminVolunteerActionOut = {
  id: 1,
  athlete_id: 42,
  athlete_nom: "LEMÉE",
  athlete_prenom: "Jean-Marc",
  season: 2025,
  title: "Ravitaillement",
  description: "Poste eau km 15.",
  status: "en_attente",
  declared_by_user_id: 7,
  created_at: "2026-08-28T13:00:00Z",
};

const SANS_TITRE: AdminVolunteerActionOut = {
  id: 2,
  athlete_id: 43,
  athlete_nom: "KERMARREC",
  athlete_prenom: "Hadrien",
  season: 2024,
  title: null,
  description: null,
  status: "en_attente",
  declared_by_user_id: null,
  created_at: "2025-06-01T13:00:00Z",
};

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <DangerConfirmProvider>
        <AdminVolunteerActionsTable />
      </DangerConfirmProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("AdminVolunteerActionsTable", () => {
  it("affiche un squelette pendant le chargement", () => {
    listPendingVolunteerActions.mockReturnValue(new Promise(() => {}));

    afficher();

    expect(screen.getByTestId("admin-volunteer-actions-skeleton")).toBeInTheDocument();
  });

  it("distingue un refus d'une liste vide", async () => {
    listPendingVolunteerActions.mockRejectedValue(new Error("Boum"));

    afficher();

    expect(await screen.findByText(/n'ont pas pu être charg/i)).toBeInTheDocument();
  });

  it("affiche un état vide explicite sans déclaration en attente", async () => {
    listPendingVolunteerActions.mockResolvedValue([]);

    afficher();

    expect(await screen.findByText(/aucune déclaration/i)).toBeInTheDocument();
  });

  it("affiche l'athlète, le titre, la description et les boutons Accepter/Refuser", async () => {
    listPendingVolunteerActions.mockResolvedValue([EN_ATTENTE]);

    afficher();

    expect(await screen.findByText(/lemée/i)).toBeInTheDocument();
    expect(screen.getByText(/jean-marc/i)).toBeInTheDocument();
    expect(screen.getByText("Ravitaillement")).toBeInTheDocument();
    expect(screen.getByText("Poste eau km 15.")).toBeInTheDocument();
    // La saison créditée, sans quoi une déclaration tardive compte en silence
    // pour la saison suivante (#956).
    expect(screen.getByRole("columnheader", { name: "Saison" })).toBeInTheDocument();
    expect(screen.getByText(seasonLabel(2025))).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /accepter/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /refuser/i })).toBeInTheDocument();
  });

  it("affiche un repli pour une ligne historique sans titre ni description", async () => {
    listPendingVolunteerActions.mockResolvedValue([SANS_TITRE]);

    afficher();

    expect(await screen.findByText(/kermarrec/i)).toBeInTheDocument();
    const replis = await screen.findAllByText("—");
    expect(replis).toHaveLength(2);
  });

  it("accepter retire la ligne de la liste", async () => {
    listPendingVolunteerActions.mockResolvedValueOnce([EN_ATTENTE]).mockResolvedValueOnce([]);
    acceptVolunteerAction.mockResolvedValue({ ...EN_ATTENTE, status: "validee" });

    afficher();
    const bouton = await screen.findByRole("button", { name: /accepter/i });
    await userEvent.click(bouton);

    await waitFor(() => expect(acceptVolunteerAction).toHaveBeenCalledWith(1));
    await waitFor(() => expect(screen.queryByText("Ravitaillement")).not.toBeInTheDocument());
  });

  it("refuser retire la ligne de la liste", async () => {
    listPendingVolunteerActions.mockResolvedValueOnce([EN_ATTENTE]).mockResolvedValueOnce([]);
    rejectVolunteerAction.mockResolvedValue({ ...EN_ATTENTE, status: "refusee" });

    afficher();
    const bouton = await screen.findByRole("button", { name: /refuser/i });
    await userEvent.click(bouton);

    await waitFor(() => expect(rejectVolunteerAction).toHaveBeenCalledWith(1));
    await waitFor(() => expect(screen.queryByText("Ravitaillement")).not.toBeInTheDocument());
  });

  it("supprimer demande une confirmation avant d'agir", async () => {
    listPendingVolunteerActions.mockResolvedValue([EN_ATTENTE]);

    afficher();
    await userEvent.click(await screen.findByRole("button", { name: /supprimer/i }));

    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    expect(deleteVolunteerAction).not.toHaveBeenCalled();
  });

  it("annuler la confirmation laisse la ligne intacte", async () => {
    listPendingVolunteerActions.mockResolvedValue([EN_ATTENTE]);

    afficher();
    await userEvent.click(await screen.findByRole("button", { name: /supprimer/i }));
    await confirmerDansLeDialog("Renoncer");

    expect(deleteVolunteerAction).not.toHaveBeenCalled();
    expect(screen.getByText("Ravitaillement")).toBeInTheDocument();
  });

  it("confirmer supprime la déclaration et retire la ligne", async () => {
    listPendingVolunteerActions.mockResolvedValueOnce([EN_ATTENTE]).mockResolvedValueOnce([]);
    deleteVolunteerAction.mockResolvedValue(null);

    afficher();
    await userEvent.click(await screen.findByRole("button", { name: /supprimer/i }));
    await confirmerDansLeDialog("Supprimer définitivement");

    await waitFor(() => expect(deleteVolunteerAction).toHaveBeenCalledWith(1));
    await waitFor(() => expect(screen.queryByText("Ravitaillement")).not.toBeInTheDocument());
  });

  it("Voir ouvre le détail avec le texte complet, la saison, la date et la fiche athlète", async () => {
    const description = "Poste eau km 15.\nPuis balisage du parcours vélo jusqu'à la fin de l'épreuve.";
    listPendingVolunteerActions.mockResolvedValue([{ ...EN_ATTENTE, description }]);

    afficher();
    await userEvent.click(await screen.findByRole("button", { name: /voir/i }));

    const dialogue = await screen.findByRole("dialog");
    expect(within(dialogue).getByRole("heading", { name: "Ravitaillement" })).toBeInTheDocument();
    const texte = within(dialogue).getByText((_, element) => element?.textContent === description);
    expect(texte).toHaveClass("whitespace-pre-wrap");
    expect(within(dialogue).getByText(new RegExp(seasonLabel(2025)))).toBeInTheDocument();
    expect(within(dialogue).getByText(new RegExp(formatDate(EN_ATTENTE.created_at)))).toBeInTheDocument();
    expect(within(dialogue).getByRole("link", { name: /jean-marc lemée/i })).toHaveAttribute(
      "href",
      "/athletes/42",
    );
  });

  it("accepter depuis le détail appelle la mutation et ferme le dialogue", async () => {
    listPendingVolunteerActions.mockResolvedValueOnce([EN_ATTENTE]).mockResolvedValueOnce([]);
    acceptVolunteerAction.mockResolvedValue({ ...EN_ATTENTE, status: "validee" });

    afficher();
    await userEvent.click(await screen.findByRole("button", { name: /voir/i }));
    const dialogue = await screen.findByRole("dialog");
    await userEvent.click(within(dialogue).getByRole("button", { name: /accepter/i }));

    await waitFor(() => expect(acceptVolunteerAction).toHaveBeenCalledWith(1));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("refuser depuis le détail appelle la mutation et ferme le dialogue", async () => {
    listPendingVolunteerActions.mockResolvedValueOnce([EN_ATTENTE]).mockResolvedValueOnce([]);
    rejectVolunteerAction.mockResolvedValue({ ...EN_ATTENTE, status: "refusee" });

    afficher();
    await userEvent.click(await screen.findByRole("button", { name: /voir/i }));
    const dialogue = await screen.findByRole("dialog");
    await userEvent.click(within(dialogue).getByRole("button", { name: /refuser/i }));

    await waitFor(() => expect(rejectVolunteerAction).toHaveBeenCalledWith(1));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("garde le détail ouvert, boutons inertes, tant que la décision n'a pas abouti", async () => {
    listPendingVolunteerActions.mockResolvedValue([EN_ATTENTE]);
    let echouer: (e: Error) => void = () => {};
    acceptVolunteerAction.mockReturnValue(new Promise((_, rejeter) => (echouer = rejeter)));

    afficher();
    await userEvent.click(await screen.findByRole("button", { name: /voir/i }));
    const dialogue = await screen.findByRole("dialog");
    await userEvent.click(within(dialogue).getByRole("button", { name: /accepter/i }));

    await waitFor(() =>
      expect(within(screen.getByRole("dialog")).getByRole("button", { name: /accepter/i })).toBeDisabled(),
    );
    expect(within(screen.getByRole("dialog")).getByRole("button", { name: /refuser/i })).toBeDisabled();

    echouer(new Error("Refusé par le serveur"));

    await waitFor(() => expect(toastError).toHaveBeenCalledWith("Refusé par le serveur"));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("désactive Accepter et Refuser pendant qu'une suppression est en cours", async () => {
    listPendingVolunteerActions.mockResolvedValue([EN_ATTENTE]);
    let resoudre: (v: null) => void = () => {};
    deleteVolunteerAction.mockReturnValue(new Promise((r) => (resoudre = r)));

    afficher();
    await userEvent.click(await screen.findByRole("button", { name: /supprimer/i }));
    await confirmerDansLeDialog("Supprimer définitivement");

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /accepter/i })).toBeDisabled(),
    );
    expect(screen.getByRole("button", { name: /refuser/i })).toBeDisabled();

    resoudre(null);
  });
});
