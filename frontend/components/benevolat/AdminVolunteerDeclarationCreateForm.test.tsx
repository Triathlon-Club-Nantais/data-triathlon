import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { AdminUser, SessionUser } from "@/lib/types";
import { AdminVolunteerDeclarationCreateForm } from "./AdminVolunteerDeclarationCreateForm";

const { listAdminUsers, adminCreateVolunteerDeclaration, getSession } = vi.hoisted(() => ({
  listAdminUsers: vi.fn(),
  adminCreateVolunteerDeclaration: vi.fn(),
  getSession: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: { ...original.apiClient, listAdminUsers, adminCreateVolunteerDeclaration, getSession },
  };
});

const { toastSuccess, toastError } = vi.hoisted(() => ({
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}));
vi.mock("sonner", () => ({ toast: { success: toastSuccess, error: toastError } }));

const MEMBRE: AdminUser = {
  id: 17,
  email: "jean@exemple.fr",
  display_name: "Jean Dupont",
  is_active: true,
  roles: [],
  created_at: "2026-01-01T00:00:00Z",
};

const GESTIONNAIRE: SessionUser = {
  id: 1,
  email: "admin@exemple.fr",
  display_name: "Admin",
  created_at: "2026-01-01T00:00:00Z",
  permissions: ["benevolat:manage"],
  roles: [],
  groups: [],
};

const LECTEUR: SessionUser = { ...GESTIONNAIRE, permissions: ["benevolat:read"] };

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <AdminVolunteerDeclarationCreateForm />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  listAdminUsers.mockResolvedValue([MEMBRE]);
  getSession.mockResolvedValue(GESTIONNAIRE);
});

describe("AdminVolunteerDeclarationCreateForm", () => {
  it("n'affiche pas le formulaire à un titulaire du seul pouvoir de lecture", async () => {
    getSession.mockResolvedValue(LECTEUR);

    afficher();

    expect(await screen.findByText(/en consultation/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /déclarer pour ce membre/i })).not.toBeInTheDocument();
  });

  it("refuse la soumission sans membre choisi", async () => {
    afficher();
    await userEvent.type(await screen.findByLabelText("Titre"), "T");
    await userEvent.type(screen.getByLabelText("Description"), "D");
    await userEvent.click(screen.getByRole("button", { name: /déclarer pour ce membre/i }));

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(adminCreateVolunteerDeclaration).not.toHaveBeenCalled();
  });

  it("crée une déclaration validée d'office pour le membre choisi", async () => {
    adminCreateVolunteerDeclaration.mockResolvedValue({
      id: 1,
      title: "T",
      description: "D",
      status: "validee",
      beneficiary_user_id: 17,
      author_user_id: 1,
      created_at: "2026-08-30T16:00:00Z",
      beneficiary_display_name: "Jean Dupont",
      beneficiary_email: "jean@exemple.fr",
    });

    afficher();
    await screen.findByText("Jean Dupont");
    await userEvent.selectOptions(screen.getByLabelText("Membre"), "17");
    await userEvent.type(screen.getByLabelText("Titre"), "T");
    await userEvent.type(screen.getByLabelText("Description"), "D");
    await userEvent.click(screen.getByRole("button", { name: /déclarer pour ce membre/i }));

    await waitFor(() =>
      expect(adminCreateVolunteerDeclaration).toHaveBeenCalledWith({
        beneficiary_user_id: 17,
        title: "T",
        description: "D",
      }),
    );
    expect(toastSuccess).toHaveBeenCalled();
  });
});
