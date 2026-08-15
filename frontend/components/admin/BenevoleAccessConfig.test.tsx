import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiError } from "@/lib/api/client";

const {
  getBenevoleAccessConfig,
  replaceBenevoleAccessPassword,
  generateBenevoleAccessPassword,
  toastError,
  toastSuccess,
  writeText,
} = vi.hoisted(() => ({
  getBenevoleAccessConfig: vi.fn(),
  replaceBenevoleAccessPassword: vi.fn(),
  generateBenevoleAccessPassword: vi.fn(),
  toastError: vi.fn(),
  toastSuccess: vi.fn(),
  writeText: vi.fn(),
}));

vi.mock("sonner", () => ({ toast: { error: toastError, success: toastSuccess } }));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: {
      getBenevoleAccessConfig,
      replaceBenevoleAccessPassword,
      generateBenevoleAccessPassword,
    },
  };
});

Object.assign(navigator, { clipboard: { writeText } });

import { BenevoleAccessConfig } from "./BenevoleAccessConfig";

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <BenevoleAccessConfig />
    </QueryClientProvider>,
  );
}

describe("BenevoleAccessConfig", () => {
  beforeEach(() => {
    getBenevoleAccessConfig.mockReset();
    replaceBenevoleAccessPassword.mockReset();
    generateBenevoleAccessPassword.mockReset();
    toastError.mockReset();
    toastSuccess.mockReset();
    writeText.mockReset();
  });

  it("affiche « non configuré » avant tout réglage", async () => {
    getBenevoleAccessConfig.mockResolvedValue({
      configured: false,
      updated_at: null,
      updated_by: null,
    });
    afficher();

    expect(await screen.findByText(/non configuré/i)).toBeInTheDocument();
  });

  it("affiche l'auteur du dernier remplacement quand configuré", async () => {
    getBenevoleAccessConfig.mockResolvedValue({
      configured: true,
      updated_at: new Date().toISOString(),
      updated_by: "Iris Admin",
    });
    afficher();

    expect(await screen.findByText(/configuré/i)).toBeInTheDocument();
    expect(await screen.findByText(/Iris Admin/)).toBeInTheDocument();
  });

  it("remplace le mot de passe par une saisie", async () => {
    getBenevoleAccessConfig.mockResolvedValue({
      configured: false,
      updated_at: null,
      updated_by: null,
    });
    replaceBenevoleAccessPassword.mockResolvedValue({
      configured: true,
      updated_at: new Date().toISOString(),
      updated_by: "Iris Admin",
    });
    afficher();
    await screen.findByText(/non configuré/i);

    await userEvent.type(
      screen.getByLabelText(/nouveau mot de passe/i),
      "un-secret-assez-long",
    );
    await userEvent.click(screen.getByRole("button", { name: /^remplacer$/i }));

    await waitFor(() =>
      expect(replaceBenevoleAccessPassword).toHaveBeenCalledWith("un-secret-assez-long"),
    );
    expect(toastSuccess).toHaveBeenCalled();
  });

  it("le mot de passe généré s'affiche une seule fois, avec une action de copie", async () => {
    getBenevoleAccessConfig.mockResolvedValue({
      configured: false,
      updated_at: null,
      updated_by: null,
    });
    generateBenevoleAccessPassword.mockResolvedValue({
      password: "mot-de-passe-genere-abc123",
      updated_at: new Date().toISOString(),
      updated_by: "Iris Admin",
    });
    afficher();
    await screen.findByText(/non configuré/i);

    await userEvent.click(
      screen.getByRole("button", { name: /générer un mot de passe sécurisé/i }),
    );

    expect(await screen.findByText("mot-de-passe-genere-abc123")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /copier/i }));
    expect(writeText).toHaveBeenCalledWith("mot-de-passe-genere-abc123");
  });

  it("un remplacement suivant efface le mot de passe généré affiché", async () => {
    getBenevoleAccessConfig.mockResolvedValue({
      configured: false,
      updated_at: null,
      updated_by: null,
    });
    generateBenevoleAccessPassword.mockResolvedValue({
      password: "genere-une-fois",
      updated_at: new Date().toISOString(),
      updated_by: "Iris Admin",
    });
    replaceBenevoleAccessPassword.mockResolvedValue({
      configured: true,
      updated_at: new Date().toISOString(),
      updated_by: "Iris Admin",
    });
    afficher();
    await screen.findByText(/non configuré/i);
    await userEvent.click(
      screen.getByRole("button", { name: /générer un mot de passe sécurisé/i }),
    );
    await screen.findByText("genere-une-fois");

    await userEvent.type(
      screen.getByLabelText(/nouveau mot de passe/i),
      "un-autre-secret",
    );
    await userEvent.click(screen.getByRole("button", { name: /^remplacer$/i }));

    await waitFor(() => expect(screen.queryByText("genere-une-fois")).not.toBeInTheDocument());
  });

  it("un refus de l'API se traduit en message, sans planter l'écran", async () => {
    getBenevoleAccessConfig.mockResolvedValue({
      configured: false,
      updated_at: null,
      updated_by: null,
    });
    replaceBenevoleAccessPassword.mockRejectedValue(new ApiError(403, "Accès refusé"));
    afficher();
    await screen.findByText(/non configuré/i);

    await userEvent.type(
      screen.getByLabelText(/nouveau mot de passe/i),
      "un-secret-assez-long",
    );
    await userEvent.click(screen.getByRole("button", { name: /^remplacer$/i }));

    await waitFor(() => expect(toastError).toHaveBeenCalled());
  });
});
