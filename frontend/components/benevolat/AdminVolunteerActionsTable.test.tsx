import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { AdminVolunteerActionOut } from "@/lib/types";
import { AdminVolunteerActionsTable } from "./AdminVolunteerActionsTable";

const { listPendingVolunteerActions, acceptVolunteerAction, rejectVolunteerAction } = vi.hoisted(
  () => ({
    listPendingVolunteerActions: vi.fn(),
    acceptVolunteerAction: vi.fn(),
    rejectVolunteerAction: vi.fn(),
  }),
);

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: {
      ...original.apiClient,
      listPendingVolunteerActions,
      acceptVolunteerAction,
      rejectVolunteerAction,
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

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <AdminVolunteerActionsTable />
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
    expect(screen.getByRole("button", { name: /accepter/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /refuser/i })).toBeInTheDocument();
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
});
