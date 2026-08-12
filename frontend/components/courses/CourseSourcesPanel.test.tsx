import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiError } from "@/lib/api/client";
import type { CourseSource, SessionUser } from "@/lib/types";

const { getSession, switchCourseSource } = vi.hoisted(() => ({
  getSession: vi.fn(),
  switchCourseSource: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { getSession, switchCourseSource } };
});

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
    switchCourseSource.mockResolvedValue(APRES_BASCULE);
    const user = userEvent.setup();
    afficher(DEUX_SOURCES);

    await user.click(await screen.findByRole("button", { name: /activer.*breizh chrono/i }));
    await user.click(await screen.findByRole("button", { name: /^basculer$/i }));

    await waitFor(() => expect(switchCourseSource).toHaveBeenCalledWith(42, 2));
    await waitFor(() => expect(toastSuccess).toHaveBeenCalled());
    // La source désormais active (Breizh Chrono) porte le label "Source active".
    const actif = await screen.findByRole("link", { name: /breizh chrono/i });
    expect(actif).toHaveAttribute("href", "https://exemple.fr/passif");
  });

  it("annuler ne bascule rien", async () => {
    getSession.mockResolvedValue(ADMIN);
    const user = userEvent.setup();
    afficher(DEUX_SOURCES);

    await user.click(await screen.findByRole("button", { name: /activer.*breizh chrono/i }));
    await user.click(await screen.findByRole("button", { name: /annuler/i }));

    expect(switchCourseSource).not.toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: /^basculer$/i })).not.toBeInTheDocument();
  });

  it("notifie l'échec sans modifier l'affichage (scrape en échec, 422)", async () => {
    getSession.mockResolvedValue(ADMIN);
    switchCourseSource.mockRejectedValue(new ApiError(422, "Le scrape n'a renvoyé aucun résultat"));
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
});
