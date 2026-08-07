import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiError } from "@/lib/api/client";
import type { AllowedEmail } from "@/lib/types";

const { listAllowedEmails, addAllowedEmail, removeAllowedEmail } = vi.hoisted(() => ({
  listAllowedEmails: vi.fn(),
  addAllowedEmail: vi.fn(),
  removeAllowedEmail: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: { listAllowedEmails, addAllowedEmail, removeAllowedEmail },
  };
});

import { AllowedEmailsTable } from "./AllowedEmailsTable";

const ADRESSE: AllowedEmail = {
  id: 1,
  email: "contributeur@exemple.fr",
  created_at: "2026-08-01T14:54:28Z",
  created_by_name: "Camille Durand",
};

function afficher() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <AllowedEmailsTable />
    </QueryClientProvider>,
  );
}

describe("AllowedEmailsTable", () => {
  beforeEach(() => {
    listAllowedEmails.mockReset();
    addAllowedEmail.mockReset();
    removeAllowedEmail.mockReset();
    vi.spyOn(window, "confirm").mockReturnValue(true);
  });

  it("affiche les adresses autorisées et qui les a inscrites", async () => {
    listAllowedEmails.mockResolvedValue([ADRESSE]);

    afficher();

    expect(await screen.findByText(ADRESSE.email)).toBeInTheDocument();
    expect(screen.getByText(/camille durand/i)).toBeInTheDocument();
  });

  it("dit « aucune adresse autorisée » sur une liste vide", async () => {
    listAllowedEmails.mockResolvedValue([]);

    afficher();

    expect(await screen.findByText(/aucune adresse autorisée/i)).toBeInTheDocument();
  });

  it("dit « accès refusé » sur un 403, et non « aucune adresse »", async () => {
    // Même défaut que celui fermé sur PendingProvidersTable : sur un refus,
    // `data` est `undefined`. Ici l'écran mentirait sur *qui a accès* — pire
    // encore, puisqu'on pourrait en conclure que personne n'est autorisé.
    listAllowedEmails.mockRejectedValue(new ApiError(403, "Refusé"));

    afficher();

    expect(await screen.findByText(/accès refusé/i)).toBeInTheDocument();
    expect(screen.queryByText(/aucune adresse autorisée/i)).not.toBeInTheDocument();
  });

  it("distingue la session expirée du refus de droit", async () => {
    listAllowedEmails.mockRejectedValue(new ApiError(401, "Non connecté"));

    afficher();

    expect(await screen.findByText(/session expirée/i)).toBeInTheDocument();
    expect(screen.queryByText(/accès refusé/i)).not.toBeInTheDocument();
  });

  it("inscrit une adresse depuis le formulaire", async () => {
    listAllowedEmails.mockResolvedValue([]);
    addAllowedEmail.mockResolvedValue(ADRESSE);

    afficher();
    await screen.findByText(/aucune adresse autorisée/i);
    await userEvent.type(
      screen.getByLabelText(/adresse/i),
      "contributeur@exemple.fr",
    );
    await userEvent.click(screen.getByRole("button", { name: /ajouter/i }));

    await waitFor(() =>
      expect(addAllowedEmail).toHaveBeenCalledWith("contributeur@exemple.fr"),
    );
  });

  it("retire une adresse", async () => {
    listAllowedEmails.mockResolvedValue([ADRESSE]);
    removeAllowedEmail.mockResolvedValue(null);

    afficher();
    await screen.findByText(ADRESSE.email);
    await userEvent.click(screen.getByRole("button", { name: /retirer/i }));

    await waitFor(() => expect(removeAllowedEmail).toHaveBeenCalledWith(ADRESSE.id));
  });

  it("ne retire rien si la confirmation est refusée", async () => {
    // Le retrait coupe des sessions vivantes : un clic accidentel ne doit pas
    // suffire, même si le geste est réversible.
    vi.spyOn(window, "confirm").mockReturnValue(false);
    listAllowedEmails.mockResolvedValue([ADRESSE]);

    afficher();
    await screen.findByText(ADRESSE.email);
    await userEvent.click(screen.getByRole("button", { name: /retirer/i }));

    expect(removeAllowedEmail).not.toHaveBeenCalled();
  });

  it("affiche le refus du dernier administrateur tel que rendu par l'API", async () => {
    // 409 : l'appelant est bien administrateur, c'est le résultat qui est
    // interdit. Le message vient du serveur — le front ne le réécrit pas.
    listAllowedEmails.mockResolvedValue([ADRESSE]);
    removeAllowedEmail.mockRejectedValue(
      new ApiError(409, "Cette organisation perdrait son dernier administrateur."),
    );

    afficher();
    await screen.findByText(ADRESSE.email);
    await userEvent.click(screen.getByRole("button", { name: /retirer/i }));

    await waitFor(() => expect(removeAllowedEmail).toHaveBeenCalled());
    expect(await screen.findByText(ADRESSE.email)).toBeInTheDocument();
  });

  it("n'envoie rien sur un formulaire vide", async () => {
    listAllowedEmails.mockResolvedValue([]);

    afficher();
    await screen.findByText(/aucune adresse autorisée/i);
    await userEvent.click(screen.getByRole("button", { name: /ajouter/i }));

    expect(addAllowedEmail).not.toHaveBeenCalled();
  });
});
