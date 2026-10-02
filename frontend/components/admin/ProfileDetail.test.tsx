import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import type { ProfileDetail as ProfileDetailType, SessionUser } from "@/lib/types";

vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

const { getProfile, updateProfile, addProfileLogEntry, getSession } = vi.hoisted(() => ({
  getProfile: vi.fn(),
  updateProfile: vi.fn(),
  addProfileLogEntry: vi.fn(),
  getSession: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: { getProfile, updateProfile, addProfileLogEntry, getSession },
  };
});

import { ApiError } from "@/lib/api/client";
import { DangerConfirmProvider } from "@/components/admin/DangerConfirm";
import { ProfileDetail } from "./ProfileDetail";

const PROFIL: ProfileDetailType = {
  id: 1,
  organisation_id: 1,
  first_name: "Alix",
  last_name: "Martin",
  birth_date: "2015-04-12",
  created_at: "2026-01-01T00:00:00Z",
  emergency_contact: "Mère — 06 00 00 00 00",
  notes: "Allergie aux fruits à coque.",
  membership_ended_on: null,
  log_entries: [
    {
      id: 2,
      entry_date: "2026-06-01",
      text: "Entrée récente",
      created_by_name: "Encadrant Un",
      created_at: "2026-06-01T10:00:00Z",
    },
    {
      id: 1,
      entry_date: "2026-01-01",
      text: "Entrée ancienne",
      created_by_name: "Encadrant Deux",
      created_at: "2026-01-01T10:00:00Z",
    },
  ],
};

const AVEC_ECRITURE: SessionUser = {
  id: 1,
  email: "moi@exemple.fr",
  display_name: "Moi",
  created_at: "2026-01-01T00:00:00Z",
  permissions: ["jeunes:read", "jeunes:write"],
  roles: [],
  groups: [],
  can_administer: true,
};

const LECTURE_SEULE: SessionUser = { ...AVEC_ECRITURE, permissions: ["jeunes:read"] };

function afficher(id = 1) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <DangerConfirmProvider>
        <ProfileDetail profileId={id} />
      </DangerConfirmProvider>
    </QueryClientProvider>,
  );
}

describe("ProfileDetail", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getSession.mockResolvedValue(AVEC_ECRITURE);
    getProfile.mockResolvedValue(PROFIL);
  });

  it("affiche les informations personnelles", async () => {
    afficher();

    expect(await screen.findByText("Alix Martin")).toBeInTheDocument();
    expect(screen.getByText(/Mère — 06 00 00 00 00/)).toBeInTheDocument();
    expect(screen.getByText(/Allergie aux fruits à coque/)).toBeInTheDocument();
  });

  it("dit qu'un profil absent est introuvable", async () => {
    getProfile.mockRejectedValue(new ApiError(404, "Ce profil n'existe pas."));

    afficher(999);

    expect(await screen.findByText("Profil introuvable")).toBeInTheDocument();
  });

  it("affiche le journal, le plus récent en premier", async () => {
    afficher();

    const entrees = await screen.findAllByText(/^Entrée /);
    expect(entrees.map((n) => n.textContent)).toEqual(["Entrée récente", "Entrée ancienne"]);
  });

  it("affiche un message quand le journal est vide", async () => {
    getProfile.mockResolvedValue({ ...PROFIL, log_entries: [] });

    afficher();

    expect(await screen.findByText(/aucune entrée/i)).toBeInTheDocument();
  });

  it("propose l'ajout d'une entrée à un porteur de jeunes:write", async () => {
    afficher();

    expect(await screen.findByRole("button", { name: /ajouter/i })).toBeInTheDocument();
  });

  it("n'affiche aucun formulaire d'édition sans jeunes:write", async () => {
    getSession.mockResolvedValue(LECTURE_SEULE);

    afficher();

    await screen.findByText("Alix Martin");
    expect(screen.queryByRole("button", { name: /ajouter/i })).not.toBeInTheDocument();
  });

  it("corrige nom, prénom et date de naissance", async () => {
    updateProfile.mockResolvedValue(PROFIL);
    const utilisateur = userEvent.setup();

    afficher();
    await utilisateur.click(await screen.findByRole("button", { name: /modifier le profil/i }));
    const prenom = screen.getByLabelText(/prénom/i);
    const nom = screen.getByLabelText(/^nom/i);
    const naissance = screen.getByLabelText(/date de naissance/i);
    expect(prenom).toHaveValue("Alix");
    expect(naissance).toHaveValue("2015-04-12");
    await utilisateur.clear(prenom);
    await utilisateur.type(prenom, "Alice");
    await utilisateur.clear(nom);
    await utilisateur.type(nom, "Martins");
    await utilisateur.clear(naissance);
    await utilisateur.type(naissance, "2015-05-13");
    await utilisateur.click(screen.getByRole("button", { name: /enregistrer/i }));

    await waitFor(() =>
      expect(updateProfile).toHaveBeenCalledWith(
        1,
        expect.objectContaining({
          first_name: "Alice",
          last_name: "Martins",
          birth_date: "2015-05-13",
        }),
      ),
    );
  });

  it("annonce la date de suppression d'un profil dont l'adhésion a pris fin (#1158)", async () => {
    getProfile.mockResolvedValue({ ...PROFIL, membership_ended_on: "2026-06-30" });
    afficher();
    expect((await screen.findByText(/fin d'adhésion/i)).parentElement).toHaveTextContent("30/06/2026");
    expect(screen.getByText(/supprimé automatiquement à partir du 01\/09\/2027/i)).toBeInTheDocument();
  });

  it("renseigne puis efface la fin d'adhésion (#1158)", async () => {
    updateProfile.mockResolvedValue(PROFIL);
    const utilisateur = userEvent.setup();

    afficher();
    await utilisateur.click(await screen.findByRole("button", { name: /modifier le profil/i }));
    await utilisateur.type(screen.getByLabelText(/fin d'adhésion/i), "2026-06-30");
    await utilisateur.click(screen.getByRole("button", { name: /enregistrer/i }));
    await waitFor(() =>
      expect(updateProfile).toHaveBeenCalledWith(1, expect.objectContaining({ membership_ended_on: "2026-06-30" })),
    );

    getProfile.mockResolvedValue({ ...PROFIL, membership_ended_on: "2026-06-30" });
    await utilisateur.click(await screen.findByRole("button", { name: /modifier le profil/i }));
    await utilisateur.clear(screen.getByLabelText(/fin d'adhésion/i));
    await utilisateur.click(screen.getByRole("button", { name: /enregistrer/i }));
    await waitFor(() =>
      expect(updateProfile).toHaveBeenLastCalledWith(1, expect.objectContaining({ membership_ended_on: null })),
    );
  });

  it("annonce la date de suppression pendant la saisie de la fin d'adhésion (#1158)", async () => {
    const utilisateur = userEvent.setup();
    afficher();
    await utilisateur.click(await screen.findByRole("button", { name: /modifier le profil/i }));
    await utilisateur.type(screen.getByLabelText(/fin d'adhésion/i), "2099-06-30");
    expect(screen.getByText(/supprimé automatiquement à partir du 01\/09\/2100/i)).toBeInTheDocument();
  });

  it("demande confirmation quand la fin d'adhésion rend le profil supprimable tout de suite (#1158)", async () => {
    const utilisateur = userEvent.setup();
    afficher();
    await utilisateur.click(await screen.findByRole("button", { name: /modifier le profil/i }));
    await utilisateur.type(screen.getByLabelText(/fin d'adhésion/i), "2016-06-30");
    await utilisateur.click(screen.getByRole("button", { name: /enregistrer/i }));

    const dialogue = await screen.findByRole("dialog");
    expect(dialogue).toHaveTextContent(/prochaine purge/i);
    await utilisateur.click(screen.getByRole("button", { name: "Renoncer" }));
    expect(updateProfile).not.toHaveBeenCalled();
  });

  it("renseigne la date de naissance d'un profil qui n'en avait pas", async () => {
    getProfile.mockResolvedValue({ ...PROFIL, birth_date: null });
    updateProfile.mockResolvedValue(PROFIL);
    const utilisateur = userEvent.setup();

    afficher();
    expect(await screen.findByText(/âge inconnu/i)).toBeInTheDocument();
    await utilisateur.click(screen.getByRole("button", { name: /modifier le profil/i }));
    await utilisateur.type(screen.getByLabelText(/date de naissance/i), "2015-04-12");
    await utilisateur.click(screen.getByRole("button", { name: /enregistrer/i }));

    await waitFor(() =>
      expect(updateProfile).toHaveBeenCalledWith(
        1,
        expect.objectContaining({ birth_date: "2015-04-12" }),
      ),
    );
  });

  it("ajoute une entrée de journal", async () => {
    addProfileLogEntry.mockResolvedValue(PROFIL);
    const utilisateur = userEvent.setup();

    afficher();
    await screen.findByRole("button", { name: /ajouter/i });
    await utilisateur.type(screen.getByLabelText(/nouvelle entrée/i), "Bonne séance");
    await utilisateur.click(screen.getByRole("button", { name: /ajouter/i }));

    await waitFor(() =>
      expect(addProfileLogEntry).toHaveBeenCalledWith(1, "Bonne séance", expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/)),
    );
  });
});
