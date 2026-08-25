import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiError } from "@/lib/api/client";
import type { Feedback, FeedbackCounts, SessionUser } from "@/lib/types";

vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

const { listFeedback, countFeedback, updateFeedbackStatus, getFeedback, getSession } = vi.hoisted(
  () => ({
    listFeedback: vi.fn(),
    countFeedback: vi.fn(),
    updateFeedbackStatus: vi.fn(),
    getFeedback: vi.fn(),
    getSession: vi.fn(),
  }),
);

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: { listFeedback, countFeedback, updateFeedbackStatus, getFeedback, getSession },
  };
});

import { FeedbackTable } from "./FeedbackTable";

const SIGNALEMENT: Feedback = {
  id: 1,
  type: "bug",
  title: "Le classement n'affiche pas mon temps",
  body: "Après l'import, mon temps total reste vide.",
  page_url: "https://tcn.example/courses/123",
  user_agent: "Mozilla/5.0",
  status: "nouveau",
  github_url: null,
  created_at: "2026-08-01T14:54:28Z",
  email: null,
};

const COMPTES: FeedbackCounts = {
  nouveau: 7,
  en_cours: 2,
  traite: 12,
  ignore: 3,
  total: 24,
};

const INSTRUCTEUR: SessionUser = {
  id: 1,
  email: "moi@exemple.fr",
  display_name: "Moi",
  created_at: "2026-01-01T00:00:00Z",
  permissions: ["feedback:read", "feedback:manage"],
  roles: [],
  groups: [],
};

const LECTEUR: SessionUser = { ...INSTRUCTEUR, permissions: ["feedback:read"] };

function afficher() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <FeedbackTable />
    </QueryClientProvider>,
  );
}

/** Le bouton d'un filtre, sans dépendre du décompte accolé à son libellé. */
function filtre(nom: RegExp) {
  return within(screen.getByRole("group", { name: /filtrer par statut/i })).getByRole("button", {
    name: nom,
  });
}

describe("FeedbackTable", () => {
  beforeEach(() => {
    listFeedback.mockReset();
    countFeedback.mockReset();
    updateFeedbackStatus.mockReset();
    getFeedback.mockReset();
    getSession.mockReset();
    listFeedback.mockResolvedValue([SIGNALEMENT]);
    countFeedback.mockResolvedValue(COMPTES);
    updateFeedbackStatus.mockResolvedValue({ ...SIGNALEMENT, status: "traite" });
    getFeedback.mockResolvedValue(SIGNALEMENT);
    getSession.mockResolvedValue(INSTRUCTEUR);
  });

  it("affiche les colonnes date, type, titre et statut", async () => {
    afficher();

    expect(await screen.findByText(SIGNALEMENT.title)).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /date/i })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /^type/i })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /titre/i })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /statut/i })).toBeInTheDocument();
  });

  it("change le tri au clic sur un en-tête", async () => {
    afficher();
    await screen.findByText(SIGNALEMENT.title);
    listFeedback.mockClear();

    fireEvent.click(screen.getByRole("button", { name: /^type/i }));

    await waitFor(() => expect(listFeedback).toHaveBeenCalledWith("type", "desc", "nouveau"));
  });

  it("inverse l'ordre sur un second clic de la même colonne", async () => {
    afficher();
    await screen.findByText(SIGNALEMENT.title);

    fireEvent.click(screen.getByRole("button", { name: /^date/i }));
    await waitFor(() =>
      expect(listFeedback).toHaveBeenCalledWith("created_at", "asc", "nouveau"),
    );
  });

  it("dit « accès refusé » sur un 403", async () => {
    listFeedback.mockRejectedValue(new ApiError(403, "Refusé"));

    afficher();

    expect(await screen.findByText(/accès refusé/i)).toBeInTheDocument();
  });

  // --- La file de traitement (#500) ------------------------------------------

  describe("filtre par statut", () => {
    it("n'ouvre que les nouveaux : c'est la question que l'écran répond", async () => {
      afficher();

      await waitFor(() =>
        expect(listFeedback).toHaveBeenCalledWith("created_at", "desc", "nouveau"),
      );
    });

    it("bascule sur un autre statut au clic", async () => {
      afficher();
      await screen.findByText(SIGNALEMENT.title);
      listFeedback.mockClear();

      fireEvent.click(filtre(/^traité/i));

      await waitFor(() =>
        expect(listFeedback).toHaveBeenCalledWith("created_at", "desc", "traite"),
      );
    });

    it("« Tous » retire le filtre plutôt que d'en poser un cinquième", async () => {
      afficher();
      await screen.findByText(SIGNALEMENT.title);
      listFeedback.mockClear();

      fireEvent.click(filtre(/^tous/i));

      await waitFor(() =>
        expect(listFeedback).toHaveBeenCalledWith("created_at", "desc", undefined),
      );
    });

    it("dit lequel est actif", async () => {
      afficher();
      await screen.findByText(SIGNALEMENT.title);

      expect(filtre(/^nouveau/i)).toHaveAttribute("aria-pressed", "true");
      expect(filtre(/^traité/i)).toHaveAttribute("aria-pressed", "false");
    });

    it("porte le décompte de chaque statut — le « N nouveaux » de la file", async () => {
      afficher();

      expect(await screen.findByRole("button", { name: /nouveau.*7/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /traité.*12/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /tous.*24/i })).toBeInTheDocument();
    });

    it("reste montée sur un résultat vide, sans quoi le filtre est une impasse", async () => {
      listFeedback.mockResolvedValue([]);

      afficher();

      expect(await screen.findByText(/aucun signalement/i)).toBeInTheDocument();
      expect(filtre(/^tous/i)).toBeInTheDocument();
    });

    it("ne dit « aucun retour utilisateur » que si la base l'est vraiment", async () => {
      // Vue filtrée vide + décomptes qui n'ont pas encore répondu : la base
      // n'est pas en cause, et elle le serait encore moins si le comptage
      // échouait pour de bon.
      listFeedback.mockResolvedValue([]);
      countFeedback.mockRejectedValue(new ApiError(500, "Indisponible"));

      afficher();

      expect(await screen.findByText(/aucun signalement sous ce filtre/i)).toBeInTheDocument();
      expect(screen.queryByText(/aucun retour utilisateur/i)).not.toBeInTheDocument();
    });

    it("offre la sortie du filtre plutôt que de la nommer", async () => {
      listFeedback.mockResolvedValue([]);

      afficher();
      fireEvent.click(await screen.findByRole("button", { name: /voir tous les signalements/i }));

      await waitFor(() =>
        expect(listFeedback).toHaveBeenCalledWith("created_at", "desc", undefined),
      );
    });

    it("dit « aucun retour utilisateur » sur une base réellement vide", async () => {
      listFeedback.mockResolvedValue([]);
      countFeedback.mockResolvedValue({
        nouveau: 0,
        en_cours: 0,
        traite: 0,
        ignore: 0,
        total: 0,
      });

      afficher();

      expect(await screen.findByText(/aucun retour utilisateur/i)).toBeInTheDocument();
    });

    it("reste montée sur un refus, pour la même raison", async () => {
      listFeedback.mockRejectedValue(new ApiError(403, "Refusé"));

      afficher();

      await screen.findByText(/accès refusé/i);
      expect(filtre(/^tous/i)).toBeInTheDocument();
    });
  });

  describe("statut en ligne", () => {
    it("porte une couleur propre, pas le même poids visuel que les autres", async () => {
      getSession.mockResolvedValue(LECTEUR);
      listFeedback.mockResolvedValue([
        SIGNALEMENT,
        { ...SIGNALEMENT, id: 2, title: "Écarté", status: "ignore" },
      ]);

      afficher();

      // Dans le tableau, pas dans la barre : celle-ci porte les mêmes libellés.
      const tableau = within(await screen.findByRole("table"));
      const nouveau = tableau.getByText("Nouveau");
      const ignore = tableau.getByText("Ignoré");
      expect(nouveau.className).not.toBe(ignore.className);
      // L'accent le plus fort au seul statut qui demande un geste ;
      // `--tcn-danger` est l'orange de marque, pas un rouge d'erreur.
      expect(nouveau.className).toMatch(/tcn-danger/);
      expect(ignore.className).toMatch(/tcn-text-faint/);
    });

    it("se change sans ouvrir la modale — dix signalements, dix gestes", async () => {
      afficher();
      const controle = await screen.findByRole("combobox", {
        name: new RegExp(SIGNALEMENT.title.slice(0, 20), "i"),
      });

      fireEvent.change(controle, { target: { value: "traite" } });

      await waitFor(() =>
        expect(updateFeedbackStatus).toHaveBeenCalledWith(1, { status: "traite" }),
      );
    });

    it("ne désactive pas le contrôle en vol — le focus survit au geste", async () => {
      // Un navigateur retire le focus d'un contrôle qui devient `disabled` :
      // instruire au clavier repartirait du haut du document à chaque ligne.
      let resoudre: (v: unknown) => void = () => {};
      updateFeedbackStatus.mockReturnValue(new Promise((r) => (resoudre = r)));

      afficher();
      const controle = await screen.findByRole("combobox", { name: /statut de/i });
      fireEvent.change(controle, { target: { value: "traite" } });

      await waitFor(() => expect(controle).toHaveAttribute("aria-busy", "true"));
      expect(controle).not.toBeDisabled();
      resoudre({ ...SIGNALEMENT, status: "traite" });
    });

    it("repose le focus sur le filtre quand la ligne quitte la vue", async () => {
      afficher();
      const controle = await screen.findByRole("combobox", { name: /statut de/i });

      fireEvent.change(controle, { target: { value: "traite" } });

      await waitFor(() => expect(filtre(/^nouveau/i)).toHaveFocus());
    });

    it("ne fait pas disparaître la modale quand la liste se vide sous elle", async () => {
      // Instruire depuis la modale le dernier signalement d'un filtre vide la
      // liste : rendue dans la seule branche nominale, la modale s'escamoterait
      // avant qu'on ait pu promouvoir le signalement en issue.
      afficher();
      fireEvent.click(await screen.findByRole("button", { name: SIGNALEMENT.title }));
      const modale = within(await screen.findByRole("dialog"));

      // La liste que le succès de la mutation ira rechercher ne portera plus
      // ce signalement : son statut ne correspond plus au filtre.
      listFeedback.mockResolvedValue([]);
      fireEvent.change(modale.getByLabelText("Statut"), { target: { value: "traite" } });

      expect(await screen.findByText(/aucun signalement sous ce filtre/i)).toBeInTheDocument();
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });

    it("reste une lecture pour qui n'a pas « feedback:manage »", async () => {
      getSession.mockResolvedValue(LECTEUR);

      afficher();

      const tableau = within(await screen.findByRole("table"));
      expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
      expect(tableau.getByText("Nouveau")).toBeInTheDocument();
    });
  });
});
