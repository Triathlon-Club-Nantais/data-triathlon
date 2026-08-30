import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import type { CourseSource, SessionUser } from "@/lib/types";

const { getSession, switchSourceEventStream, rescrapeEventStream, deleteCourseSource } =
  vi.hoisted(() => ({
    getSession: vi.fn(),
    switchSourceEventStream: vi.fn(),
    rescrapeEventStream: vi.fn(),
    deleteCourseSource: vi.fn(),
  }));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { getSession, deleteCourseSource } };
});

vi.mock("@/lib/api/sse", () => ({ rescrapeEventStream, switchSourceEventStream }));

const { toastSuccess, toastError } = vi.hoisted(() => ({
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}));
vi.mock("sonner", () => ({ toast: { success: toastSuccess, error: toastError } }));

import { CourseSourcesPanel } from "./CourseSourcesPanel";

const ADMIN: SessionUser = {
  id: 1,
  email: "admin@exemple.fr",
  permissions: ["courses:sources"],
  roles: [],
  created_at: "2026-01-01T00:00:00Z",
} as unknown as SessionUser;

const ANONYME = null;

const UNE_SOURCE: CourseSource[] = [
  { id: 1, url: "https://exemple.fr/x", provider: "klikego", is_active: true, last_scraped_at: null },
];

const DEUX_SOURCES: CourseSource[] = [
  { id: 1, url: "https://exemple.fr/actif", provider: "klikego", is_active: true, last_scraped_at: null },
  { id: 2, url: "https://exemple.fr/passif", provider: "breizhchrono", is_active: false, last_scraped_at: null },
];

function afficher(sources: CourseSource[]) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <CourseSourcesPanel courseId={42} initialSources={sources} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

/** Flux contrôlable : la « saving » est yield immédiatement, le « done »
 * n'arrive qu'après `release()` — pour observer la barre de progression avant
 * la fin de l'opération sans dépendre d'un timing incertain. */
function fluxControle(fin: object) {
  let liberer: () => void;
  const porte = new Promise<void>((resolve) => {
    liberer = resolve;
  });
  async function* generateur() {
    yield { phase: "saving", total: 10, imported: 2, updated: 1, skipped: 0, progress: 3 };
    await porte;
    yield fin;
  }
  return { generateur: generateur(), liberer: () => liberer() };
}

describe("CourseSourcesPanel", () => {
  it("n'affiche rien pour une épreuve sans source", () => {
    getSession.mockResolvedValue(ANONYME);
    const { container } = afficher([]);
    expect(container).toBeEmptyDOMElement();
  });

  it("affiche une unique source sans bouton, même pour un porteur du pouvoir", async () => {
    getSession.mockResolvedValue(ADMIN);
    afficher(UNE_SOURCE);

    expect(await screen.findByText("Klikego")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /activer/i })).not.toBeInTheDocument();
  });

  it("ne propose aucun bouton « Activer » à un visiteur anonyme", async () => {
    getSession.mockResolvedValue(ANONYME);
    afficher(DEUX_SOURCES);

    await screen.findByText("Breizh Chrono");
    expect(screen.queryByRole("button", { name: /activer/i })).not.toBeInTheDocument();
  });

  it("propose « Activer » sur la source passive à un porteur de courses:sources", async () => {
    getSession.mockResolvedValue(ADMIN);
    afficher(DEUX_SOURCES);

    expect(await screen.findByRole("button", { name: /activer.*breizh chrono/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /activer.*klikego/i })).not.toBeInTheDocument();
  });

  it("bascule après confirmation, réaffiche la liste renvoyée et notifie le succès", async () => {
    getSession.mockResolvedValue(ADMIN);
    const APRES_BASCULE: CourseSource[] = [
      { id: 2, url: "https://exemple.fr/passif", provider: "breizhchrono", is_active: true, last_scraped_at: "2026-08-12T10:00:00Z" },
      { id: 1, url: "https://exemple.fr/actif", provider: "klikego", is_active: false, last_scraped_at: null },
    ];
    async function* flux() {
      yield {
        phase: "done", participations_deleted: 2, participations_imported: 1,
        athletes_purged: 0, sources: APRES_BASCULE,
      };
    }
    switchSourceEventStream.mockReturnValue(flux());
    const user = userEvent.setup();
    afficher(DEUX_SOURCES);

    await user.click(await screen.findByRole("button", { name: /activer.*breizh chrono/i }));
    await user.click(await screen.findByRole("button", { name: /^basculer$/i }));

    await waitFor(() => expect(switchSourceEventStream).toHaveBeenCalledWith(42, 2));
    await waitFor(() => expect(toastSuccess).toHaveBeenCalled());
    // La source désormais active (Breizh Chrono) porte le label "Source active".
    const actif = await screen.findByRole("link", { name: /breizh chrono/i });
    expect(actif).toHaveAttribute("href", "https://exemple.fr/passif");
  });

  it("affiche la progression pendant la bascule avant de notifier le succès", async () => {
    getSession.mockResolvedValue(ADMIN);
    let liberer!: () => void;
    const porte = new Promise<void>((resolve) => {
      liberer = resolve;
    });
    async function* flux() {
      yield { phase: "scraping", message: "Récupération des participants…" };
      await porte;
      yield {
        phase: "done", participations_deleted: 2, participations_imported: 1,
        athletes_purged: 0, sources: DEUX_SOURCES,
      };
    }
    switchSourceEventStream.mockReturnValue(flux());
    const user = userEvent.setup();
    afficher(DEUX_SOURCES);

    await user.click(await screen.findByRole("button", { name: /activer.*breizh chrono/i }));
    await user.click(await screen.findByRole("button", { name: /^basculer$/i }));

    await screen.findByText(/récupération des participants/i);
    liberer();

    await waitFor(() => expect(toastSuccess).toHaveBeenCalled());
  });

  it("annuler ne bascule rien", async () => {
    getSession.mockResolvedValue(ADMIN);
    const user = userEvent.setup();
    afficher(DEUX_SOURCES);

    await user.click(await screen.findByRole("button", { name: /activer.*breizh chrono/i }));
    await user.click(await screen.findByRole("button", { name: /annuler/i }));

    expect(switchSourceEventStream).not.toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: /^basculer$/i })).not.toBeInTheDocument();
  });

  it("notifie l'échec sans modifier l'affichage (scrape en échec)", async () => {
    getSession.mockResolvedValue(ADMIN);
    async function* flux() {
      yield { phase: "error", message: "Le scrape n'a renvoyé aucun résultat" };
    }
    switchSourceEventStream.mockReturnValue(flux());
    const user = userEvent.setup();
    afficher(DEUX_SOURCES);

    await user.click(await screen.findByRole("button", { name: /activer.*breizh chrono/i }));
    await user.click(await screen.findByRole("button", { name: /^basculer$/i }));

    await waitFor(() =>
      expect(toastError).toHaveBeenCalledWith("Le scrape n'a renvoyé aucun résultat"),
    );
    // Toujours Klikego l'actif, rien n'a bougé.
    const actif = screen.getByRole("link", { name: /klikego/i });
    expect(actif).toHaveAttribute("href", "https://exemple.fr/actif");
  });

  // --- Re-scraper à la demande (#118) --------------------------------------

  it("ne propose aucun bouton « Re-scraper » à un visiteur anonyme", async () => {
    getSession.mockResolvedValue(ANONYME);
    afficher(UNE_SOURCE);

    await screen.findByText("Klikego");
    expect(screen.queryByRole("button", { name: /re-scraper/i })).not.toBeInTheDocument();
  });

  it("propose « Re-scraper » sur l'unique source à un porteur de courses:sources", async () => {
    getSession.mockResolvedValue(ADMIN);
    afficher(UNE_SOURCE);

    expect(await screen.findByRole("button", { name: /re-scraper/i })).toBeInTheDocument();
  });

  it("affiche la progression pendant le flux et un succès en fin d'opération", async () => {
    getSession.mockResolvedValue(ADMIN);
    const { generateur, liberer } = fluxControle({
      phase: "done", imported: 3, updated: 7, skipped: 0,
      reconciled: 0, total: 10, orphans_removed: 1,
    });
    rescrapeEventStream.mockReturnValue(generateur);
    const user = userEvent.setup();
    afficher(UNE_SOURCE);

    await user.click(await screen.findByRole("button", { name: /re-scraper/i }));

    await screen.findByText(/enregistrement des résultats/i);
    await screen.findByText("3/10");
    liberer();

    await waitFor(() =>
      expect(toastSuccess).toHaveBeenCalledWith(
        "Résultats à jour : 3 ajoutés, 7 mis à jour (sur 10 participants).",
      ),
    );
  });

  it("dit clairement « déjà à jour » plutôt que « 0 ajoutés, 0 mis à jour » quand rien n'a changé", async () => {
    getSession.mockResolvedValue(ADMIN);
    const { generateur, liberer } = fluxControle({
      phase: "done", imported: 0, updated: 0, skipped: 586,
      reconciled: 0, total: 586, orphans_removed: 0,
    });
    rescrapeEventStream.mockReturnValue(generateur);
    const user = userEvent.setup();
    afficher(UNE_SOURCE);

    await user.click(await screen.findByRole("button", { name: /re-scraper/i }));
    liberer();

    await waitFor(() =>
      expect(toastSuccess).toHaveBeenCalledWith(
        "Déjà à jour — 586 participants vérifiés, aucun changement chez le chronométreur.",
      ),
    );
  });

  it("notifie l'échec sans modifier l'affichage (zéro résultat, refusé)", async () => {
    getSession.mockResolvedValue(ADMIN);
    const { generateur, liberer } = fluxControle({
      phase: "error",
      message: "Le chronométreur n'a publié aucun résultat à cette adresse.",
    });
    rescrapeEventStream.mockReturnValue(generateur);
    const user = userEvent.setup();
    afficher(UNE_SOURCE);

    await user.click(await screen.findByRole("button", { name: /re-scraper/i }));
    liberer();

    await waitFor(() =>
      expect(toastError).toHaveBeenCalledWith(
        "Le chronométreur n'a publié aucun résultat à cette adresse.",
      ),
    );
  });

  it("place « Re-scraper » sur la source active uniquement, jamais sur une passive", async () => {
    getSession.mockResolvedValue(ADMIN);
    afficher(DEUX_SOURCES);

    await screen.findByRole("button", { name: /activer.*breizh chrono/i });
    const boutons = screen.getAllByRole("button", { name: /re-scraper/i });
    expect(boutons).toHaveLength(1);
  });

  // --- Supprimer une source inactive (#739) --------------------------------

  it("ne propose aucun bouton « Supprimer » sur l'unique source (toujours active)", async () => {
    getSession.mockResolvedValue(ADMIN);
    afficher(UNE_SOURCE);

    await screen.findByText("Klikego");
    expect(screen.queryByRole("button", { name: /supprimer/i })).not.toBeInTheDocument();
  });

  it("ne propose aucun bouton « Supprimer » à un visiteur anonyme", async () => {
    getSession.mockResolvedValue(ANONYME);
    afficher(DEUX_SOURCES);

    await screen.findByText("Breizh Chrono");
    expect(screen.queryByRole("button", { name: /supprimer/i })).not.toBeInTheDocument();
  });

  it("propose « Supprimer » sur la source passive, jamais sur l'active", async () => {
    getSession.mockResolvedValue(ADMIN);
    afficher(DEUX_SOURCES);

    expect(
      await screen.findByRole("button", { name: /supprimer.*breizh chrono/i }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /supprimer.*klikego/i }),
    ).not.toBeInTheDocument();
  });

  it("supprime après confirmation, retire la source de l'affichage et notifie le succès", async () => {
    getSession.mockResolvedValue(ADMIN);
    deleteCourseSource.mockResolvedValue(undefined);
    const user = userEvent.setup();
    afficher(DEUX_SOURCES);

    await user.click(await screen.findByRole("button", { name: /supprimer.*breizh chrono/i }));
    await user.click(await screen.findByRole("button", { name: /supprimer définitivement/i }));

    await waitFor(() => expect(deleteCourseSource).toHaveBeenCalledWith(42, 2));
    await waitFor(() => expect(toastSuccess).toHaveBeenCalled());
    expect(screen.queryByText("Breizh Chrono")).not.toBeInTheDocument();
    expect(await screen.findByText("Klikego")).toBeInTheDocument();
  });

  it("annuler ne supprime rien", async () => {
    getSession.mockResolvedValue(ADMIN);
    const user = userEvent.setup();
    afficher(DEUX_SOURCES);

    await user.click(await screen.findByRole("button", { name: /supprimer.*breizh chrono/i }));
    await user.click(await screen.findByRole("button", { name: /renoncer/i }));

    expect(deleteCourseSource).not.toHaveBeenCalled();
    expect(await screen.findByText("Breizh Chrono")).toBeInTheDocument();
  });

  it("notifie l'échec de suppression sans modifier l'affichage", async () => {
    getSession.mockResolvedValue(ADMIN);
    deleteCourseSource.mockRejectedValue(new Error("Impossible de supprimer la source active."));
    const user = userEvent.setup();
    afficher(DEUX_SOURCES);

    await user.click(await screen.findByRole("button", { name: /supprimer.*breizh chrono/i }));
    await user.click(await screen.findByRole("button", { name: /supprimer définitivement/i }));

    await waitFor(() =>
      expect(toastError).toHaveBeenCalledWith("Impossible de supprimer la source active."),
    );
    expect(await screen.findByText("Breizh Chrono")).toBeInTheDocument();
  });
});
