import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Participation, SessionUser } from "@/lib/types";

const { getSession, detachParticipations, push, toastSuccess, toastError } = vi.hoisted(() => ({
  getSession: vi.fn(),
  detachParticipations: vi.fn(),
  push: vi.fn(),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { getSession, detachParticipations } };
});
vi.mock("sonner", () => ({ toast: { success: toastSuccess, error: toastError } }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push, refresh: vi.fn() }) }));

import { AthleteDetachAction } from "./AthleteDetachAction";

function session(permissions: string[]): SessionUser {
  return { id: 1, email: "a@exemple.fr", permissions, roles: [], created_at: "2026-01-01T00:00:00Z" } as unknown as SessionUser;
}

const RESULTAT = (id: number, nom: string, club: string | null) =>
  ({ id, club, course: { id: id * 10, name: nom, event_date: "2026-05-16" } }) as unknown as Participation;

const RESULTATS = [RESULTAT(1, "Tri Nantes", "Triathlon Club Nantais"), RESULTAT(2, "Tri Vendôme", "Vendôme Triathlon")];

function afficher(participations = RESULTATS) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <AthleteDetachAction athleteId={7} athleteName="MARTIN Thomas" participations={participations} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  document.cookie = "tcn_logged_in=1; path=/";
});

describe("AthleteDetachAction", () => {
  it("n'est pas offert sans les deux pouvoirs", async () => {
    getSession.mockResolvedValue(session(["athletes:write"]));
    afficher();
    await vi.waitFor(() => expect(getSession).toHaveBeenCalled());
    expect(screen.queryByRole("button", { name: /séparer/i })).not.toBeInTheDocument();
  });

  it("n'est pas offert avec le seul pouvoir de rattachement", async () => {
    getSession.mockResolvedValue(session(["participations:reassign"]));
    afficher();
    await vi.waitFor(() => expect(getSession).toHaveBeenCalled());
    expect(screen.queryByRole("button", { name: /séparer/i })).not.toBeInTheDocument();
  });

  it("n'est pas offert sur une fiche à un seul résultat", async () => {
    getSession.mockResolvedValue(session(["athletes:write", "participations:reassign"]));
    afficher([RESULTATS[0]]);
    await vi.waitFor(() => expect(getSession).toHaveBeenCalled());
    expect(screen.queryByRole("button", { name: /séparer/i })).not.toBeInTheDocument();
  });

  it("sépare les résultats cochés après confirmation, puis ouvre la nouvelle fiche", async () => {
    getSession.mockResolvedValue(session(["athletes:write", "participations:reassign"]));
    detachParticipations.mockResolvedValue({ id: 42, nom: "MARTIN", prenom: "Thomas" });
    afficher();

    await userEvent.click(await screen.findByRole("button", { name: "Séparer des résultats de MARTIN Thomas" }));
    const choix = await screen.findByRole("dialog");
    const envoi = within(choix).getByRole("button", { name: "Séparer vers une nouvelle fiche" });
    expect(envoi).toBeDisabled();
    await userEvent.click(within(choix).getByRole("checkbox", { name: /Tri Vendôme/ }));
    await userEvent.click(envoi);

    const confirmation = await screen.findByRole("dialog", { name: /Séparer 1 résultat/ });
    await userEvent.click(within(confirmation).getByRole("button", { name: "Séparer" }));

    expect(detachParticipations).toHaveBeenCalledWith(7, [2]);
    expect(push).toHaveBeenCalledWith("/athletes/42");
    expect(toastSuccess).toHaveBeenCalled();
  });

  it("tout cocher laisse l'envoi inerte : la fiche doit garder un résultat", async () => {
    getSession.mockResolvedValue(session(["athletes:write", "participations:reassign"]));
    afficher();

    await userEvent.click(await screen.findByRole("button", { name: /Séparer des résultats/ }));
    const choix = await screen.findByRole("dialog");
    for (const caseACocher of within(choix).getAllByRole("checkbox")) await userEvent.click(caseACocher);

    expect(within(choix).getByRole("button", { name: "Séparer vers une nouvelle fiche" })).toBeDisabled();
    expect(within(choix).getByText(/garder au moins un résultat/i)).toBeInTheDocument();
  });
});
