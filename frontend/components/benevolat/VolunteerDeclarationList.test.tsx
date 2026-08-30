import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { VolunteerDeclaration } from "@/lib/types";
import { DangerConfirmProvider } from "@/components/admin/DangerConfirm";
import { confirmerDansLeDialog } from "@/components/admin/__tests__/dangerConfirm";
import { VolunteerDeclarationList } from "./VolunteerDeclarationList";

const { listMyVolunteerDeclarations, deleteMyVolunteerDeclaration } = vi.hoisted(() => ({
  listMyVolunteerDeclarations: vi.fn(),
  deleteMyVolunteerDeclaration: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: { ...original.apiClient, listMyVolunteerDeclarations, deleteMyVolunteerDeclaration },
  };
});

const { toastSuccess, toastError } = vi.hoisted(() => ({
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}));
vi.mock("sonner", () => ({ toast: { success: toastSuccess, error: toastError } }));

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <DangerConfirmProvider>
        <VolunteerDeclarationList />
      </DangerConfirmProvider>
    </QueryClientProvider>,
  );
}

const DECLARATION: VolunteerDeclaration = {
  id: 1,
  title: "Ravitaillement",
  description: "Poste eau, 10km du Lac",
  status: "en_attente",
  beneficiary_user_id: 7,
  author_user_id: 7,
  created_at: "2026-08-30T16:00:00Z",
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe("VolunteerDeclarationList", () => {
  it("affiche un état vide sans déclaration", async () => {
    listMyVolunteerDeclarations.mockResolvedValue([]);

    afficher();

    expect(await screen.findByText(/aucune déclaration de bénévolat/i)).toBeInTheDocument();
  });

  it("affiche le titre et le statut d'une déclaration en attente", async () => {
    listMyVolunteerDeclarations.mockResolvedValue([DECLARATION]);

    afficher();

    expect(await screen.findByText("Ravitaillement")).toBeInTheDocument();
    expect(screen.getByText("En attente de validation")).toBeInTheDocument();
  });

  it("affiche le statut validée", async () => {
    listMyVolunteerDeclarations.mockResolvedValue([{ ...DECLARATION, status: "validee" }]);

    afficher();

    expect(await screen.findByText("Validée")).toBeInTheDocument();
  });

  it("supprime une déclaration après confirmation", async () => {
    listMyVolunteerDeclarations.mockResolvedValue([DECLARATION]);
    deleteMyVolunteerDeclaration.mockResolvedValue(undefined);

    afficher();
    await userEvent.click(await screen.findByRole("button", { name: /supprimer/i }));
    await confirmerDansLeDialog(/^Supprimer$/);

    await waitFor(() => expect(deleteMyVolunteerDeclaration).toHaveBeenCalledWith(1));
    expect(toastSuccess).toHaveBeenCalled();
  });

  it("n'appelle pas la suppression si l'utilisateur annule", async () => {
    listMyVolunteerDeclarations.mockResolvedValue([DECLARATION]);

    afficher();
    await userEvent.click(await screen.findByRole("button", { name: /supprimer/i }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: /renoncer/i }));

    expect(deleteMyVolunteerDeclaration).not.toHaveBeenCalled();
  });
});
