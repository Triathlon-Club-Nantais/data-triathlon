import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import type { Feedback, SessionUser } from "@/lib/types";

vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

const { getFeedback, updateFeedbackStatus, updateFeedbackGithubUrl, getSession } = vi.hoisted(
  () => ({
    getFeedback: vi.fn(),
    updateFeedbackStatus: vi.fn(),
    updateFeedbackGithubUrl: vi.fn(),
    getSession: vi.fn(),
  }),
);

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: { getFeedback, updateFeedbackStatus, updateFeedbackGithubUrl, getSession },
  };
});

import { FeedbackDetailDialog } from "./FeedbackDetailDialog";

const SIGNALEMENT_ANONYME: Feedback = {
  id: 1,
  type: "bug",
  title: "Le classement n'affiche pas mon temps",
  body: "Après l'import de l'épreuve X, mon temps total reste vide.",
  page_url: "https://tcn.example/courses/123",
  user_agent: "Mozilla/5.0",
  status: "nouveau",
  github_url: null,
  created_at: "2026-08-01T14:54:28Z",
  email: null,
};

const SIGNALEMENT_CONNECTE: Feedback = {
  ...SIGNALEMENT_ANONYME,
  id: 2,
  email: "camille@exemple.fr",
};

const MOI: SessionUser = {
  id: 1,
  email: "moi@exemple.fr",
  display_name: "Moi",
  created_at: "2026-01-01T00:00:00Z",
  permissions: ["feedback:read", "feedback:manage"],
  roles: [],
  groups: [],
};

function afficher(signalement: Feedback) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <FeedbackDetailDialog feedback={signalement} open onOpenChange={() => {}} />
    </QueryClientProvider>,
  );
}

describe("FeedbackDetailDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getSession.mockResolvedValue(MOI);
    getFeedback.mockResolvedValue(SIGNALEMENT_ANONYME);
  });

  it("affiche le titre, la description et le contexte", async () => {
    afficher(SIGNALEMENT_ANONYME);

    expect(await screen.findByText(SIGNALEMENT_ANONYME.title)).toBeInTheDocument();
    expect(screen.getByText(SIGNALEMENT_ANONYME.body)).toBeInTheDocument();
    expect(screen.getByText(SIGNALEMENT_ANONYME.page_url!)).toBeInTheDocument();
  });

  it("ne mentionne aucun email pour un signalement anonyme", async () => {
    afficher(SIGNALEMENT_ANONYME);

    await screen.findByText(SIGNALEMENT_ANONYME.title);
    expect(screen.queryByText(/camille@exemple\.fr/)).not.toBeInTheDocument();
  });

  it("affiche l'email pour un signalement soumis connecté", async () => {
    getFeedback.mockResolvedValue(SIGNALEMENT_CONNECTE);

    afficher(SIGNALEMENT_CONNECTE);

    expect(await screen.findByText("camille@exemple.fr")).toBeInTheDocument();
  });

  it("change le statut via le sélecteur", async () => {
    updateFeedbackStatus.mockResolvedValue({ ...SIGNALEMENT_ANONYME, status: "traite" });

    afficher(SIGNALEMENT_ANONYME);
    await screen.findByText(SIGNALEMENT_ANONYME.title);

    await userEvent.selectOptions(await screen.findByLabelText(/statut/i), "traite");

    await waitFor(() =>
      expect(updateFeedbackStatus).toHaveBeenCalledWith(SIGNALEMENT_ANONYME.id, {
        status: "traite",
      }),
    );
  });

  it("n'offre pas le sélecteur de statut sans feedback:manage", async () => {
    getSession.mockResolvedValue({ ...MOI, permissions: ["feedback:read"] });

    afficher(SIGNALEMENT_ANONYME);

    await screen.findByText(SIGNALEMENT_ANONYME.title);
    await waitFor(() => expect(getSession).toHaveBeenCalled());
    expect(screen.queryByLabelText(/statut/i)).not.toBeInTheDocument();
  });

  it("construit le lien de promotion avec le dépôt, le titre et le corps encodés, sans appel réseau", async () => {
    afficher(SIGNALEMENT_ANONYME);
    await screen.findByText(SIGNALEMENT_ANONYME.title);

    const lien = await screen.findByRole("link", { name: /promouvoir en issue github/i });
    const href = lien.getAttribute("href")!;
    const url = new URL(href);

    expect(url.href.startsWith("https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/new")).toBe(true);
    expect(url.searchParams.get("title")).toBe(SIGNALEMENT_ANONYME.title);
    expect(url.searchParams.get("body")).toBe(SIGNALEMENT_ANONYME.body);
    expect(lien.getAttribute("target")).toBe("_blank");
    // Un lien navigable, jamais un appel — aucune des deux fonctions d'écriture
    // ne doit avoir été déclenchée par sa seule présence.
    expect(updateFeedbackStatus).not.toHaveBeenCalled();
    expect(updateFeedbackGithubUrl).not.toHaveBeenCalled();
  });

  it("enregistre l'URL de retour collée par l'administrateur", async () => {
    updateFeedbackGithubUrl.mockResolvedValue({
      ...SIGNALEMENT_ANONYME,
      github_url: "https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/321",
    });

    afficher(SIGNALEMENT_ANONYME);
    await screen.findByText(SIGNALEMENT_ANONYME.title);

    await userEvent.type(
      await screen.findByLabelText(/url de l.issue/i),
      "https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/321",
    );
    await userEvent.click(screen.getByRole("button", { name: /enregistrer/i }));

    await waitFor(() =>
      expect(updateFeedbackGithubUrl).toHaveBeenCalledWith(
        SIGNALEMENT_ANONYME.id,
        "https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/321",
      ),
    );
  });

  it("n'offre ni promotion ni saisie d'URL sans feedback:manage", async () => {
    getSession.mockResolvedValue({ ...MOI, permissions: ["feedback:read"] });

    afficher(SIGNALEMENT_ANONYME);

    await screen.findByText(SIGNALEMENT_ANONYME.title);
    await waitFor(() => expect(getSession).toHaveBeenCalled());
    expect(screen.queryByRole("link", { name: /promouvoir/i })).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/url de l.issue/i)).not.toBeInTheDocument();
  });
});
