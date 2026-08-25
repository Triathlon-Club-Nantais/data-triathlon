import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiError } from "@/lib/api/client";
import type { Feedback, FeedbackCounts, SessionUser } from "@/lib/types";

vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

const { listFeedback, countFeedback, updateFeedbackStatus, getSession } = vi.hoisted(() => ({
  listFeedback: vi.fn(),
  countFeedback: vi.fn(),
  updateFeedbackStatus: vi.fn(),
  getSession: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: { listFeedback, countFeedback, updateFeedbackStatus, getSession },
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
    getSession.mockReset();
    listFeedback.mockResolvedValue([SIGNALEMENT]);
    countFeedback.mockResolvedValue(COMPTES);
    updateFeedbackStatus.mockResolvedValue({ ...SIGNALEMENT, status: "traite" });
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
      expect(nouveau.className).toMatch(/tcn-warning/);
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

    it("reste une lecture pour qui n'a pas « feedback:manage »", async () => {
      getSession.mockResolvedValue(LECTEUR);

      afficher();

      const tableau = within(await screen.findByRole("table"));
      expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
      expect(tableau.getByText("Nouveau")).toBeInTheDocument();
    });
  });
});
