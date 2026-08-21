import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { toast } from "sonner";
import { ApiError } from "@/lib/api/client";
import type { AllowedEmail, Role, SessionUser } from "@/lib/types";

// Même raison qu'en face : sans doublure, « le message du serveur est réaffiché »
// ne s'observe nulle part, la liste étant servie par le cache.
vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

const {
  listAllowedEmails,
  addAllowedEmail,
  removeAllowedEmail,
  listRoles,
  getSession,
  revokeSessions,
} = vi.hoisted(() => ({
  listAllowedEmails: vi.fn(),
  addAllowedEmail: vi.fn(),
  removeAllowedEmail: vi.fn(),
  listRoles: vi.fn(),
  getSession: vi.fn(),
  revokeSessions: vi.fn(),
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
      revokeSessions,
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
  permissions: ["allowed_emails:manage", "roles:read", "roles:assign"],
  roles: [],
  groups: [],
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

    // `undefined` : le sélecteur n'a pas été touché, la demande ne se prononce
    // pas. Envoyer `null` ferait de « ré-autoriser une adresse » — le geste
    // documenté pour rouvrir un compte fermé — un effacement silencieux du rôle
    // qui l'attendait.
    await waitFor(() =>
      expect(addAllowedEmail).toHaveBeenCalledWith(
        "contributeur@exemple.fr",
        undefined,
      ),
    );
  });

  it("lève le rôle quand on choisit « Aucun » explicitement", async () => {
    listAllowedEmails.mockResolvedValue([]);
    addAllowedEmail.mockResolvedValue(ADRESSE);

    afficher();
    await screen.findByText(/aucune adresse autorisée/i);
    await userEvent.type(
      screen.getByLabelText(/adresse/i),
      "contributeur@exemple.fr",
    );
    const selecteur = await screen.findByLabelText(/rôle à l'inscription/i);
    await userEvent.selectOptions(selecteur, String(BENEVOLE.id));
    await userEvent.selectOptions(selecteur, "");
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

  it("n'offre pas de rôle à l'inscription à qui ne peut pas en attribuer", async () => {
    // Donner un rôle est `roles:assign`, quel que soit le guichet — le backend
    // le refuse désormais ici aussi. Un sélecteur qui rendrait 403 à chaque
    // envoi est le mensonge qu'on vient de retirer du rail de navigation.
    getSession.mockResolvedValue({
      ...MOI,
      permissions: ["allowed_emails:manage"],
    });
    listAllowedEmails.mockResolvedValue([]);
    addAllowedEmail.mockResolvedValue(ADRESSE);

    afficher();
    await screen.findByText(/aucune adresse autorisée/i);
    await userEvent.type(
      screen.getByLabelText(/adresse/i),
      "contributeur@exemple.fr",
    );
    await userEvent.click(screen.getByRole("button", { name: /ajouter/i }));

    expect(screen.queryByLabelText(/rôle à l'inscription/i)).not.toBeInTheDocument();
    // `undefined` et non `null` : le champ est **absent** de la requête, ce que
    // le backend distingue de « aucun rôle » — lequel exige `roles:assign`.
    await waitFor(() =>
      expect(addAllowedEmail).toHaveBeenCalledWith(
        "contributeur@exemple.fr",
        undefined,
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

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith(
        "Cette organisation perdrait son dernier administrateur.",
      ),
    );
    expect(await screen.findByText(ADRESSE.email)).toBeInTheDocument();
  });

  it("empile le formulaire d'ajout en colonne sous le point de rupture sm (#479, ADM-11)", async () => {
    // À 375 px, `flex items-end gap-2` sans `flex-wrap` écrasait le champ
    // e-mail contre un `<select>` en `w-48` fixe.
    listAllowedEmails.mockResolvedValue([]);

    afficher();
    await screen.findByText(/aucune adresse autorisée/i);
    const formulaire = screen.getByLabelText(/adresse à autoriser/i).closest("form");

    expect(formulaire?.className).toMatch(/(^|\s)flex-col(\s|$)/);
    expect(formulaire?.className).toMatch(/(^|\s)sm:flex-row(\s|$)/);
  });

  it("laisse le sélecteur de rôle prendre toute la largeur sous le point de rupture sm (#479, ADM-11)", async () => {
    listAllowedEmails.mockResolvedValue([]);

    afficher();
    const selecteur = await screen.findByLabelText(/rôle à l'inscription/i);

    expect(selecteur.className).toMatch(/(^|\s)w-full(\s|$)/);
    expect(selecteur.className).not.toMatch(/(^|\s)w-48(\s|$)/);
    expect(selecteur.className).toMatch(/(^|\s)sm:w-48(\s|$)/);
  });

  it("n'envoie rien sur un formulaire vide", async () => {
    listAllowedEmails.mockResolvedValue([]);

    afficher();
    await screen.findByText(/aucune adresse autorisée/i);
    await userEvent.click(screen.getByRole("button", { name: /ajouter/i }));

    expect(addAllowedEmail).not.toHaveBeenCalled();
  });
});

describe("AllowedEmailsTable — révocation des sessions (#169)", () => {
  /** Une adresse dont quelqu'un s'est déjà servi : elle seule a des sessions. */
  const VENUE: AllowedEmail = { ...ADRESSE, has_account: true };

  const MOI_REVOCATRICE: SessionUser = {
    ...MOI,
    permissions: [...MOI.permissions, "sessions:revoke"],
  };

  beforeEach(() => {
    listAllowedEmails.mockReset();
    listRoles.mockReset();
    getSession.mockReset();
    revokeSessions.mockReset();
    listRoles.mockResolvedValue([BENEVOLE]);
    getSession.mockResolvedValue(MOI_REVOCATRICE);
    vi.spyOn(window, "confirm").mockReturnValue(true);
  });

  it("ferme les sessions de l'adresse de la ligne", async () => {
    listAllowedEmails.mockResolvedValue([VENUE]);
    revokeSessions.mockResolvedValue({ sessions: 2, accounts: 1 });
    afficher();
    await screen.findByText(VENUE.email);

    await userEvent.click(
      screen.getByRole("button", { name: /fermer les sessions de contributeur/i }),
    );

    await waitFor(() => expect(revokeSessions).toHaveBeenCalledWith(VENUE.email));
    expect(toast.success).toHaveBeenCalledWith(expect.stringContaining("2"));
  });

  it("n'offre pas le geste sur une adresse jamais venue", async () => {
    // Aucun compte, donc aucune session : un bouton y serait un geste sans objet.
    listAllowedEmails.mockResolvedValue([ADRESSE]);
    afficher();
    await screen.findByText(ADRESSE.email);

    expect(
      screen.queryByRole("button", { name: /fermer les sessions/i }),
    ).not.toBeInTheDocument();
  });

  it("n'offre pas le geste à qui n'a pas le pouvoir", async () => {
    // L'écran s'ouvre avec `allowed_emails:manage` seul : un bouton qui rendrait
    // 403 à chaque clic est pire que pas de bouton.
    getSession.mockResolvedValue(MOI);
    listAllowedEmails.mockResolvedValue([VENUE]);
    afficher();
    await screen.findByText(VENUE.email);

    expect(
      screen.queryByRole("button", { name: /fermer les sessions/i }),
    ).not.toBeInTheDocument();
  });

  it("dit ce que l'API refuse, sans inventer de second message", async () => {
    listAllowedEmails.mockResolvedValue([VENUE]);
    revokeSessions.mockRejectedValue(new ApiError(403, "Accès refusé."));
    afficher();
    await screen.findByText(VENUE.email);

    await userEvent.click(
      screen.getByRole("button", { name: /fermer les sessions de contributeur/i }),
    );

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Accès refusé."));
  });
});
