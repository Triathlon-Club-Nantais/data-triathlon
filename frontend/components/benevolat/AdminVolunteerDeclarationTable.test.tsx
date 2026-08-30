import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api/client";
import type { AdminVolunteerDeclaration, SessionUser } from "@/lib/types";
import { DangerConfirmProvider } from "@/components/admin/DangerConfirm";
import { confirmerDansLeDialog } from "@/components/admin/__tests__/dangerConfirm";
import { AdminVolunteerDeclarationTable } from "./AdminVolunteerDeclarationTable";

const { listAllVolunteerDeclarations, validateVolunteerDeclaration, adminDeleteVolunteerDeclaration, getSession } =
  vi.hoisted(() => ({
    listAllVolunteerDeclarations: vi.fn(),
    validateVolunteerDeclaration: vi.fn(),
    adminDeleteVolunteerDeclaration: vi.fn(),
    getSession: vi.fn(),
  }));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: {
      ...original.apiClient,
      listAllVolunteerDeclarations,
      validateVolunteerDeclaration,
      adminDeleteVolunteerDeclaration,
      getSession,
    },
  };
});

const { toastSuccess } = vi.hoisted(() => ({ toastSuccess: vi.fn() }));
vi.mock("sonner", () => ({ toast: { success: toastSuccess, error: vi.fn() } }));

const GESTIONNAIRE: SessionUser = {
  id: 1,
  email: "admin@exemple.fr",
  display_name: "Admin",
  created_at: "2026-01-01T00:00:00Z",
  permissions: ["benevolat:read", "benevolat:manage"],
  roles: [],
  groups: [],
};

const LECTEUR: SessionUser = { ...GESTIONNAIRE, permissions: ["benevolat:read"] };

const EN_ATTENTE: AdminVolunteerDeclaration = {
  id: 1,
  title: "Ravitaillement",
  description: "D",
  status: "en_attente",
  beneficiary_user_id: 7,
  author_user_id: 7,
  created_at: "2026-08-30T16:00:00Z",
  beneficiary_display_name: "Jean Dupont",
  beneficiary_email: "jean@exemple.fr",
};

const VALIDEE: AdminVolunteerDeclaration = { ...EN_ATTENTE, id: 2, status: "validee" };

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <DangerConfirmProvider>
        <AdminVolunteerDeclarationTable />
      </DangerConfirmProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  getSession.mockResolvedValue(GESTIONNAIRE);
});

describe("AdminVolunteerDeclarationTable", () => {
  it("dit qu'il n'y a aucune déclaration sur une liste vide", async () => {
    listAllVolunteerDeclarations.mockResolvedValue([]);

    afficher();

    expect(await screen.findByText(/aucune déclaration de bénévolat/i)).toBeInTheDocument();
  });

  it("affiche l'identité du bénéficiaire et le statut de chaque déclaration (US5)", async () => {
    listAllVolunteerDeclarations.mockResolvedValue([EN_ATTENTE, VALIDEE]);

    afficher();

    expect(await screen.findAllByText("Jean Dupont")).toHaveLength(2);
    expect(screen.getByText("En attente")).toBeInTheDocument();
    expect(screen.getByText("Validée")).toBeInTheDocument();
  });

  it("dit « accès refusé » sur un 403", async () => {
    listAllVolunteerDeclarations.mockRejectedValue(new ApiError(403, "Refusé"));

    afficher();

    expect(await screen.findByText(/accès refusé/i)).toBeInTheDocument();
  });

  it("n'offre aucune action à un titulaire du seul pouvoir de lecture", async () => {
    getSession.mockResolvedValue(LECTEUR);
    listAllVolunteerDeclarations.mockResolvedValue([EN_ATTENTE]);

    afficher();
    await screen.findByText("Ravitaillement");

    expect(screen.queryByRole("button", { name: /valider/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /supprimer/i })).not.toBeInTheDocument();
  });

  it("valide une déclaration en attente au clic", async () => {
    listAllVolunteerDeclarations.mockResolvedValue([EN_ATTENTE]);
    validateVolunteerDeclaration.mockResolvedValue({ ...EN_ATTENTE, status: "validee" });

    afficher();
    await userEvent.click(await screen.findByRole("button", { name: /valider/i }));

    await waitFor(() => expect(validateVolunteerDeclaration).toHaveBeenCalledWith(1));
    expect(toastSuccess).toHaveBeenCalled();
  });

  it("ne propose pas de valider une déclaration déjà validée", async () => {
    listAllVolunteerDeclarations.mockResolvedValue([VALIDEE]);

    afficher();
    await screen.findByText("Ravitaillement");

    expect(screen.queryByRole("button", { name: /valider/i })).not.toBeInTheDocument();
  });

  it("supprime une déclaration après confirmation", async () => {
    listAllVolunteerDeclarations.mockResolvedValue([EN_ATTENTE]);
    adminDeleteVolunteerDeclaration.mockResolvedValue(undefined);

    afficher();
    await userEvent.click(await screen.findByRole("button", { name: /supprimer/i }));
    await confirmerDansLeDialog(/^Supprimer$/);

    await waitFor(() => expect(adminDeleteVolunteerDeclaration).toHaveBeenCalledWith(1));
    expect(toastSuccess).toHaveBeenCalled();
  });
});
