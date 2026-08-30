import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { VolunteerDeclarationForm } from "./VolunteerDeclarationForm";

const { createVolunteerDeclaration } = vi.hoisted(() => ({
  createVolunteerDeclaration: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { ...original.apiClient, createVolunteerDeclaration } };
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
      <VolunteerDeclarationForm />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("VolunteerDeclarationForm", () => {
  it("refuse la soumission quand le titre est vide", async () => {
    afficher();
    await userEvent.type(screen.getByLabelText("Description"), "Une description");
    await userEvent.click(screen.getByRole("button", { name: /déclarer cette activité/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/obligatoires/i);
    expect(createVolunteerDeclaration).not.toHaveBeenCalled();
  });

  it("refuse la soumission quand la description est vide", async () => {
    afficher();
    await userEvent.type(screen.getByLabelText("Titre"), "Un titre");
    await userEvent.click(screen.getByRole("button", { name: /déclarer cette activité/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/obligatoires/i);
    expect(createVolunteerDeclaration).not.toHaveBeenCalled();
  });

  it("soumet titre et description au clic", async () => {
    createVolunteerDeclaration.mockResolvedValue({
      id: 1,
      title: "Ravitaillement",
      description: "Poste eau",
      status: "en_attente",
      beneficiary_user_id: 1,
      author_user_id: 1,
      created_at: "2026-08-30T16:00:00Z",
    });

    afficher();
    await userEvent.type(screen.getByLabelText("Titre"), "Ravitaillement");
    await userEvent.type(screen.getByLabelText("Description"), "Poste eau");
    await userEvent.click(screen.getByRole("button", { name: /déclarer cette activité/i }));

    await waitFor(() =>
      expect(createVolunteerDeclaration).toHaveBeenCalledWith({
        title: "Ravitaillement",
        description: "Poste eau",
      }),
    );
    expect(toastSuccess).toHaveBeenCalled();
  });

  it("affiche un message d'échec si la création échoue", async () => {
    createVolunteerDeclaration.mockRejectedValue(new Error("Boum"));

    afficher();
    await userEvent.type(screen.getByLabelText("Titre"), "T");
    await userEvent.type(screen.getByLabelText("Description"), "D");
    await userEvent.click(screen.getByRole("button", { name: /déclarer cette activité/i }));

    await waitFor(() => expect(toastError).toHaveBeenCalled());
  });
});
