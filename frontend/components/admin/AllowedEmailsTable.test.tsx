import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiError } from "@/lib/api/client";
import type { AllowedEmail, Role, SessionUser } from "@/lib/types";

const {
  listAllowedEmails,
  addAllowedEmail,
  removeAllowedEmail,
  listRoles,
  getSession,
} = vi.hoisted(() => ({
  listAllowedEmails: vi.fn(),
  addAllowedEmail: vi.fn(),
  removeAllowedEmail: vi.fn(),
  listRoles: vi.fn(),
  getSession: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: {
      listAllowedEmails,
      addAllowedEmail,
      removeAllowedEmail,
      listRoles,
      getSession,
    },
  };
});

import { AllowedEmailsTable } from "./AllowedEmailsTable";

const BENEVOLE: Role = {
  id: 2,
  organisation_id: 1,
  slug: "benevole",
  name: "Bénévole",
  description: "",
  is_system: false,
  is_superuser: false,
  permissions: [],
  stale_permissions: [],
  holders: 0,
};

const MOI: SessionUser = {
  id: 1,
  email: "moi@exemple.fr",
  display_name: "Moi",
  created_at: "2026-01-01T00:00:00Z",
  permissions: ["allowed_emails:manage", "roles:read"],
  roles: [],
};

const ADRESSE: AllowedEmail = {
  id: 1,
  email: "contributeur@exemple.fr",
  created_at: "2026-08-01T14:54:28Z",
  created_by_name: "Camille Durand",
  role: null,
  has_account: false,
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
    listRoles.mockReset();
    getSession.mockReset();
    listRoles.mockResolvedValue([BENEVOLE]);
    getSession.mockResolvedValue(MOI);
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
      expect(addAllowedEmail).toHaveBeenCalledWith("contributeur@exemple.fr", null),
    );
  });

  it("inscrit une adresse avec le rôle qu'elle portera à sa première connexion", async () => {
    // Le geste d'administration tenait en deux temps séparés par un événement
    // qu'on ne contrôle pas — la connexion de la personne. Il tient désormais
    // en un seul.
    listAllowedEmails.mockResolvedValue([]);
    addAllowedEmail.mockResolvedValue({ ...ADRESSE, role: BENEVOLE });

    afficher();
    await screen.findByText(/aucune adresse autorisée/i);
    await userEvent.type(
      screen.getByLabelText(/adresse/i),
      "contributeur@exemple.fr",
    );
    await userEvent.selectOptions(
      await screen.findByLabelText(/rôle à l'inscription/i),
      String(BENEVOLE.id),
    );
    await userEvent.click(screen.getByRole("button", { name: /ajouter/i }));

    await waitFor(() =>
      expect(addAllowedEmail).toHaveBeenCalledWith(
        "contributeur@exemple.fr",
        BENEVOLE.id,
      ),
    );
  });

  it("affiche le rôle initial de chaque adresse", async () => {
    listAllowedEmails.mockResolvedValue([{ ...ADRESSE, role: BENEVOLE }]);

    afficher();

    // Dans la **ligne**, pas dans le sélecteur du formulaire — qui porte le même
    // libellé.
    const ligne = await screen.findByRole("row", { name: new RegExp(ADRESSE.email) });
    expect(within(ligne).getByText(BENEVOLE.name)).toBeInTheDocument();
  });

  it("signale une adresse autorisée dont personne n'est encore venu", async () => {
    // C'est le seul retour qu'on ait sur le rôle à l'inscription : « déjà
    // appliqué » et « attend toujours » se ressemblent sans lui.
    listAllowedEmails.mockResolvedValue([{ ...ADRESSE, has_account: false }]);

    afficher();

    const ligne = await screen.findByRole("row", { name: new RegExp(ADRESSE.email) });
    expect(within(ligne).getByText(/jamais connecté/i)).toBeInTheDocument();
  });

  it("marque comme actif un compte déjà ouvert", async () => {
    listAllowedEmails.mockResolvedValue([{ ...ADRESSE, has_account: true }]);

    afficher();

    const ligne = await screen.findByRole("row", { name: new RegExp(ADRESSE.email) });
    expect(within(ligne).getByText(/compte actif/i)).toBeInTheDocument();
    expect(within(ligne).queryByText(/jamais connecté/i)).not.toBeInTheDocument();
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
