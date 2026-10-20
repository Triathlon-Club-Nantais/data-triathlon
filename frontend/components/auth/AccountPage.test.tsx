import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api/client";
import type { AccountIdentity, SessionUser } from "@/lib/types";

const { push, getSession, getMyIdentities, deleteAccount, detachAthlete, cancelAthleteClaim } = vi.hoisted(() => ({
  push: vi.fn(),
  getSession: vi.fn(),
  getMyIdentities: vi.fn(),
  deleteAccount: vi.fn(),
  detachAthlete: vi.fn(),
  cancelAthleteClaim: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/mon-compte",
  useRouter: () => ({ push, refresh: vi.fn() }),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: { getSession, getMyIdentities, deleteAccount, detachAthlete, cancelAthleteClaim },
  };
});

import { AccountPage } from "./AccountPage";

const SESSION: SessionUser = {
  id: 1,
  email: "contributeur@exemple.fr",
  display_name: "Camille Martin",
  created_at: "2026-08-01T14:54:28Z",
  permissions: [],
  roles: [],
  groups: [],
  can_administer: false,
  is_member: false,
  athlete: null,
  athlete_claim: null,
  can_supervise: false,
};

const IDENTITIES: AccountIdentity[] = [
  { provider: "github", label: "GitHub", email: "camille@github.example", created_at: "2026-08-01T14:54:28Z" },
  { provider: "google", label: "Google", email: "camille@gmail.example", created_at: "2026-09-12T08:00:00Z" },
];

const JEAN = { id: 12, prenom: "Jean", nom: "Dupont" };
const claim = (status: "pending" | "rejected") => ({ id: 3, athlete: JEAN, status, created_at: "2026-10-17T10:00:00Z" });

function afficher(session: SessionUser) {
  getSession.mockResolvedValue(session);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <AccountPage />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  getMyIdentities.mockResolvedValue(IDENTITIES);
  deleteAccount.mockResolvedValue(null);
  detachAthlete.mockResolvedValue(null);
  cancelAthleteClaim.mockResolvedValue(null);
});

describe("AccountPage: account section", () => {
  it("shows the address, display name, creation date, sign-in providers and membership", async () => {
    afficher(SESSION);

    expect(await screen.findByText(SESSION.email)).toBeInTheDocument();
    expect(screen.getByText("Camille Martin")).toBeInTheDocument();
    expect(screen.getByText("Compte créé le 01/08/2026")).toBeInTheDocument();
    expect(await screen.findByText("GitHub")).toBeInTheDocument();
    expect(screen.getByText("Google")).toBeInTheDocument();
    expect(screen.getByText("camille@github.example")).toBeInTheDocument();
    expect(screen.getByText("Non adhérent")).toBeInTheDocument();
  });

  it("names the card « Mes informations »", async () => {
    afficher(SESSION);

    expect(await screen.findByRole("heading", { name: "Mes informations" })).toBeInTheDocument();
  });

  it("says when no sign-in is recorded", async () => {
    getMyIdentities.mockResolvedValue([]);
    afficher(SESSION);

    expect(await screen.findByText("Aucune connexion enregistrée.")).toBeInTheDocument();
  });

  it("flags a failed identities read as an error and retries it", async () => {
    getMyIdentities.mockRejectedValue(new ApiError(500, "boom"));
    afficher(SESSION);

    const alerte = await screen.findByRole("alert");
    expect(alerte).toHaveTextContent("Connexions indisponibles pour le moment.");
    expect(alerte).toHaveStyle({ color: "var(--tcn-danger-text)" });
    getMyIdentities.mockResolvedValue(IDENTITIES);
    await userEvent.click(screen.getByRole("button", { name: "Réessayer" }));

    expect(await screen.findByText("GitHub")).toBeInTheDocument();
  });

  it("says « Adhérent » for a member", async () => {
    afficher({ ...SESSION, is_member: true });

    expect(await screen.findByText("Adhérent")).toBeInTheDocument();
    expect(screen.queryByText("Non adhérent")).not.toBeInTheDocument();
  });
});

describe("AccountPage: athlete record section", () => {
  it("shows the linked record, a link to Mon espace and detaches after confirmation", async () => {
    afficher({ ...SESSION, athlete: JEAN });

    expect(await screen.findByText("Jean Dupont")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ouvrir Mon espace" })).toHaveAttribute("href", "/mon-espace");
    await userEvent.click(screen.getByRole("button", { name: "Me détacher de ma fiche" }));
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveAccessibleName("Vous détacher de votre fiche ?");
    expect(detachAthlete).not.toHaveBeenCalled();

    await userEvent.click(within(dialog).getByRole("button", { name: "Me détacher" }));
    await waitFor(() => expect(detachAthlete).toHaveBeenCalled());
  });

  it("shows a pending claim and cancels it", async () => {
    afficher({ ...SESSION, athlete_claim: claim("pending") });

    expect(await screen.findByText("Demande en attente : Jean Dupont")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Annuler la demande" }));
    await waitFor(() => expect(cancelAthleteClaim).toHaveBeenCalled());
  });

  it("shows a failed cancellation in the error colour", async () => {
    cancelAthleteClaim.mockRejectedValue(new ApiError(409, "Déjà traitée."));
    afficher({ ...SESSION, athlete_claim: claim("pending") });

    await userEvent.click(await screen.findByRole("button", { name: "Annuler la demande" }));

    expect(await screen.findByRole("alert")).toHaveStyle({ color: "var(--tcn-danger-text)" });
  });

  it("says a claim was rejected, without any gesture", async () => {
    afficher({ ...SESSION, athlete_claim: claim("rejected") });

    expect(await screen.findByText("Demande refusée : Jean Dupont")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Annuler la demande" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Me détacher de ma fiche" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Mon espace/ })).toHaveAttribute("href", "/mon-espace");
  });

  it("points to Mon espace to link a record when there is neither record nor claim", async () => {
    afficher(SESSION);

    const lien = await screen.findByRole("link", { name: /rattacher/i });
    expect(lien).toHaveAttribute("href", "/mon-espace");
    expect(screen.queryByRole("button", { name: "Me détacher de ma fiche" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Annuler la demande" })).not.toBeInTheDocument();
  });
});

describe("AccountPage: sensitive zone", () => {
  async function ouvrirLaSuppression() {
    afficher(SESSION);
    const bouton = await screen.findByRole("button", { name: "Supprimer mon compte" });
    expect(bouton).toHaveClass("tcn-btn--destructive");
    await userEvent.click(bouton);
    return screen.findByRole("dialog");
  }

  it("opens the deletion dialog without any request", async () => {
    const dialog = await ouvrirLaSuppression();

    expect(dialog).toHaveAccessibleName("Supprimer votre compte ?");
    expect(dialog).toHaveTextContent(/connexions, rôles et groupes/);
    expect(deleteAccount).not.toHaveBeenCalled();
  });

  it("deletes the account then goes back to the home page", async () => {
    await ouvrirLaSuppression();
    // Après suppression, la session relue est anonyme : la page ne doit pas perdre la navigation.
    getSession.mockRejectedValue(new ApiError(401, "anonyme"));

    await userEvent.click(screen.getByRole("button", { name: "Supprimer définitivement" }));

    await waitFor(() => expect(deleteAccount).toHaveBeenCalled());
    await waitFor(() => expect(push).toHaveBeenCalledWith("/"));
    expect(screen.queryByText(/pour gérer votre compte/)).not.toBeInTheDocument();
  });

  it("shows the server refusal inside the dialog and stays put", async () => {
    deleteAccount.mockRejectedValue(new ApiError(409, "Contactez le club pour le faire supprimer."));
    const dialog = await ouvrirLaSuppression();

    await userEvent.click(screen.getByRole("button", { name: "Supprimer définitivement" }));

    await waitFor(() => expect(dialog).toHaveTextContent("Contactez le club pour le faire supprimer."));
    expect(push).not.toHaveBeenCalled();
  });
});

describe("AccountPage: session states", () => {
  it("shows a skeleton while the session is pending", async () => {
    getSession.mockReturnValue(new Promise(() => {}));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <AccountPage />
      </QueryClientProvider>,
    );

    expect(await screen.findByTestId("squelette-compte")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Supprimer mon compte" })).not.toBeInTheDocument();
  });

  it("says the session is unavailable and retries it", async () => {
    getSession.mockRejectedValue(new ApiError(503, "indisponible"));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <AccountPage />
      </QueryClientProvider>,
    );

    const reessayer = await screen.findByRole("button", { name: "Réessayer" });
    expect(screen.getByRole("alert")).toHaveTextContent(/indisponible/i);
    expect(screen.queryByRole("button", { name: "Supprimer mon compte" })).not.toBeInTheDocument();
    getSession.mockResolvedValue(SESSION);
    await userEvent.click(reessayer);

    expect(await screen.findByText(SESSION.email)).toBeInTheDocument();
  });
});
