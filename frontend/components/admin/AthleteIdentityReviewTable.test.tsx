import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiError } from "@/lib/api/client";
import { DangerConfirmProvider } from "@/components/admin/DangerConfirm";
import { confirmerDansLeDialog } from "@/components/admin/__tests__/dangerConfirm";
import type { IdentityReviewList, SessionUser } from "@/lib/types";

const { listIdentityReview, getSession, ignoreIdentityPair, toastError, toastSuccess } = vi.hoisted(() => ({
  listIdentityReview: vi.fn(),
  getSession: vi.fn(),
  ignoreIdentityPair: vi.fn(),
  toastError: vi.fn(),
  toastSuccess: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { listIdentityReview, getSession, ignoreIdentityPair } };
});
vi.mock("sonner", () => ({ toast: { error: toastError, success: toastSuccess } }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: vi.fn(), push: vi.fn() }) }));

import { AthleteIdentityReviewTable } from "./AthleteIdentityReviewTable";

function session(permissions: string[]): SessionUser {
  return { id: 1, email: "admin@exemple.fr", permissions, roles: [], created_at: "2026-01-01T00:00:00Z" } as unknown as SessionUser;
}

const FICHE = (id: number, nom: string, prenom: string, extra = {}) => ({
  id, nom, prenom, club: null, gender: "M", categories: [], participations: 1, homonym_rank: 0, ...extra,
});

const CAS: IdentityReviewList = {
  candidates: [
    {
      reason: "same_course_bibs",
      reason_label: "Deux dossards sur une même épreuve",
      athletes: [FICHE(7, "MARTIN", "Thomas", { club: "Triathlon Club Nantais", categories: ["M25-29", "M45-49"] })],
      conflicts: [
        {
          course_id: 407, course_name: "IRONMAN Tours", event_date: "2025-06-01",
          entries: [
            { participation_id: 1, athlete_id: 7, bib: "2348", category: "M25-29", total_time: "11:19:24" },
            { participation_id: 2, athlete_id: 7, bib: "1715", category: "M45-49", total_time: "11:45:59" },
          ],
        },
      ],
    },
    {
      reason: "swapped",
      reason_label: "Nom et prénom inversés",
      athletes: [FICHE(10, "DUPONT", "Jean"), FICHE(11, "JEAN", "Dupont", { homonym_rank: 0 })],
      conflicts: [],
    },
  ],
};

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <DangerConfirmProvider>
        <AthleteIdentityReviewTable />
      </DangerConfirmProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  document.cookie = "tcn_logged_in=1; path=/";
});

describe("AthleteIdentityReviewTable", () => {
  it("rend chaque cas avec son motif, ses fiches et ses épreuves en conflit", async () => {
    getSession.mockResolvedValue(session(["athletes:write", "athletes:read"]));
    listIdentityReview.mockResolvedValue(CAS);
    afficher();

    const cartes = await screen.findAllByRole("article");
    expect(cartes).toHaveLength(2);
    expect(within(cartes[0]).getByRole("heading", { level: 2, name: /MARTIN Thomas/ })).toBeInTheDocument();
    expect(within(cartes[0]).getByText(/1 épreuve en conflit/)).toBeInTheDocument();
    expect(within(cartes[0]).getByText("Deux dossards sur une même épreuve")).toBeInTheDocument();
    expect(within(cartes[0]).getByRole("link", { name: /MARTIN Thomas/ })).toHaveAttribute("href", "/athletes/7");
    expect(within(cartes[0]).getByText(/IRONMAN Tours/)).toBeInTheDocument();
    expect(within(cartes[0]).getByText(/2348/)).toBeInTheDocument();
    expect(within(cartes[0]).getByText(/1715/)).toBeInTheDocument();
  });

  it("un cas à une fiche ne s'écarte ni ne se fusionne : il se règle sur la fiche", async () => {
    getSession.mockResolvedValue(session(["athletes:write", "athletes:read"]));
    listIdentityReview.mockResolvedValue(CAS);
    afficher();

    const [unique, paire] = await screen.findAllByRole("article");
    expect(within(unique).queryByRole("button", { name: /écarter/i })).not.toBeInTheDocument();
    expect(within(unique).queryByRole("button", { name: /fusionner/i })).not.toBeInTheDocument();
    expect(within(unique).getByText(/réattribuez/i)).toBeInTheDocument();
    expect(within(paire).getByRole("button", { name: "Écarter la paire DUPONT Jean et JEAN Dupont" })).toBeInTheDocument();
    expect(within(paire).getByRole("button", { name: "Fusionner DUPONT Jean et JEAN Dupont" })).toBeInTheDocument();
  });

  it("écarter une paire demande confirmation puis l'envoie", async () => {
    getSession.mockResolvedValue(session(["athletes:write", "athletes:read"]));
    listIdentityReview.mockResolvedValue(CAS);
    ignoreIdentityPair.mockResolvedValue({ athlete_id_a: 10, athlete_id_b: 11, ignored_at: "2026-10-02T10:00:00Z" });
    afficher();

    const [, paire] = await screen.findAllByRole("article");
    await userEvent.click(within(paire).getByRole("button", { name: /écarter/i }));
    await confirmerDansLeDialog("Écarter");

    expect(ignoreIdentityPair).toHaveBeenCalledWith(10, 11);
    expect(toastSuccess).toHaveBeenCalled();
  });

  it("sans `athletes:read`, la fusion n'est pas offerte : la recherche de fiches lui manque", async () => {
    getSession.mockResolvedValue(session(["athletes:write"]));
    listIdentityReview.mockResolvedValue(CAS);
    afficher();

    const [, paire] = await screen.findAllByRole("article");
    expect(within(paire).getByRole("button", { name: /écarter/i })).toBeInTheDocument();
    expect(within(paire).queryByRole("button", { name: /fusionner/i })).not.toBeInTheDocument();
  });

  it("une liste vide le dit, un refus aussi", async () => {
    getSession.mockResolvedValue(session(["athletes:write"]));
    listIdentityReview.mockResolvedValue({ candidates: [] });
    const { unmount } = afficher();
    expect(await screen.findByText(/aucun cas d'identité/i)).toBeInTheDocument();
    unmount();

    listIdentityReview.mockRejectedValue(new ApiError(403, "Forbidden"));
    afficher();
    expect(await screen.findByText(/ne permet pas de consulter les cas d'identité/i)).toBeInTheDocument();
  });
});
