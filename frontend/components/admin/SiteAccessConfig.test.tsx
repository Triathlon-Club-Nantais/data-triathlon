import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiError } from "@/lib/api/client";

const {
  getSiteAccessConfig,
  replaceSiteAccessPassword,
  generateSiteAccessPassword,
  toastError,
  toastSuccess,
  writeText,
} = vi.hoisted(() => ({
  getSiteAccessConfig: vi.fn(),
  replaceSiteAccessPassword: vi.fn(),
  generateSiteAccessPassword: vi.fn(),
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
      getSiteAccessConfig,
      replaceSiteAccessPassword,
      generateSiteAccessPassword,
    },
  };
});

Object.assign(navigator, { clipboard: { writeText } });

import { SiteAccessConfig } from "./SiteAccessConfig";

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <SiteAccessConfig />
    </QueryClientProvider>,
  );
}

/** Saisit un mot de passe, ouvre la confirmation, puis la valide. */
async function remplacerAvecConfirmation(motDePasse: string) {
  await userEvent.type(screen.getByLabelText(/nouveau mot de passe/i), motDePasse);
  await userEvent.click(screen.getByRole("button", { name: /^remplacer$/i }));
  const dialogue = await screen.findByRole("dialog");
  await userEvent.click(
    within(dialogue).getByRole("button", { name: /^remplacer$/i }),
  );
}

describe("SiteAccessConfig", () => {
  beforeEach(() => {
    getSiteAccessConfig.mockReset();
    replaceSiteAccessPassword.mockReset();
    generateSiteAccessPassword.mockReset();
    toastError.mockReset();
    toastSuccess.mockReset();
    writeText.mockReset();
  });

  it("affiche « non configuré » avant tout réglage", async () => {
    getSiteAccessConfig.mockResolvedValue({
      configured: false,
      updated_at: null,
      updated_by: null,
    });
    afficher();

    expect(await screen.findByText(/non configuré/i)).toBeInTheDocument();
  });

  it("affiche l'auteur du dernier remplacement quand configuré", async () => {
    getSiteAccessConfig.mockResolvedValue({
      configured: true,
      updated_at: new Date().toISOString(),
      updated_by: "Iris Admin",
    });
    afficher();

    expect(await screen.findByText(/configuré/i)).toBeInTheDocument();
    expect(await screen.findByText(/Iris Admin/)).toBeInTheDocument();
  });

  it("remplace le mot de passe par une saisie", async () => {
    getSiteAccessConfig.mockResolvedValue({
      configured: false,
      updated_at: null,
      updated_by: null,
    });
    replaceSiteAccessPassword.mockResolvedValue({
      configured: true,
      updated_at: new Date().toISOString(),
      updated_by: "Iris Admin",
    });
    afficher();
    await screen.findByText(/non configuré/i);

    await remplacerAvecConfirmation("un-secret-assez-long");

    await waitFor(() =>
      expect(replaceSiteAccessPassword).toHaveBeenCalledWith("un-secret-assez-long"),
    );
    expect(toastSuccess).toHaveBeenCalled();
  });

  it("le remplacement se confirme avant d'invalider les sessions ouvertes", async () => {
    getSiteAccessConfig.mockResolvedValue({
      configured: true,
      updated_at: new Date().toISOString(),
      updated_by: "Iris Admin",
    });
    afficher();
    await screen.findByText(/^configuré$/i);

    await userEvent.type(
      screen.getByLabelText(/nouveau mot de passe/i),
      "un-secret-assez-long",
    );
    await userEvent.click(screen.getByRole("button", { name: /^remplacer$/i }));

    expect(await screen.findByRole("dialog")).toHaveTextContent(
      /toutes les sessions ouvertes cesseront/i,
    );
    expect(replaceSiteAccessPassword).not.toHaveBeenCalled();
  });

  it("renoncer à la confirmation ne remplace rien", async () => {
    getSiteAccessConfig.mockResolvedValue({
      configured: false,
      updated_at: null,
      updated_by: null,
    });
    afficher();
    await screen.findByText(/non configuré/i);

    await userEvent.type(
      screen.getByLabelText(/nouveau mot de passe/i),
      "un-secret-assez-long",
    );
    await userEvent.click(screen.getByRole("button", { name: /^remplacer$/i }));
    const dialogue = await screen.findByRole("dialog");
    await userEvent.click(within(dialogue).getByRole("button", { name: /renoncer/i }));

    expect(replaceSiteAccessPassword).not.toHaveBeenCalled();
  });

  it("le mot de passe généré s'affiche une seule fois, avec une action de copie", async () => {
    getSiteAccessConfig.mockResolvedValue({
      configured: false,
      updated_at: null,
      updated_by: null,
    });
    generateSiteAccessPassword.mockResolvedValue({
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
    getSiteAccessConfig.mockResolvedValue({
      configured: false,
      updated_at: null,
      updated_by: null,
    });
    generateSiteAccessPassword.mockResolvedValue({
      password: "genere-une-fois",
      updated_at: new Date().toISOString(),
      updated_by: "Iris Admin",
    });
    replaceSiteAccessPassword.mockResolvedValue({
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

    await remplacerAvecConfirmation("un-autre-secret");

    await waitFor(() => expect(screen.queryByText("genere-une-fois")).not.toBeInTheDocument());
  });

  it("un refus de l'API se traduit en message, sans planter l'écran", async () => {
    getSiteAccessConfig.mockResolvedValue({
      configured: false,
      updated_at: null,
      updated_by: null,
    });
    replaceSiteAccessPassword.mockRejectedValue(new ApiError(403, "Accès refusé"));
    afficher();
    await screen.findByText(/non configuré/i);

    await remplacerAvecConfirmation("un-secret-assez-long");

    await waitFor(() => expect(toastError).toHaveBeenCalled());
  });
});
