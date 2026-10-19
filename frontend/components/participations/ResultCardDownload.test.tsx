import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Participation, SessionUser } from "@/lib/types";

const { getSession, downloadResultCard } = vi.hoisted(() => ({
  getSession: vi.fn(),
  downloadResultCard: vi.fn(),
}));
vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { ...original.apiClient, getSession } };
});
vi.mock("@/lib/result-card", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/result-card")>()),
  downloadResultCard,
}));

import { ResultCardDownload } from "./ResultCardDownload";

const LEA = { id: 42, prenom: "Léa", nom: "Martin" };

const RESULTAT = {
  id: 5,
  athlete: LEA,
  course: { id: 9, name: "Triathlon de Nantes", event_date: "2026-06-07", event_type: "triathlon-m", is_relay: false },
  category: "SEF",
  rank_overall: 12,
  rank_category: 2,
  total_time: "2:10:05",
  status: "finisher",
  is_relay: false,
  is_pending_validation: false,
} as unknown as Participation;

function session(athlete: SessionUser["athlete"]): SessionUser {
  return { id: 1, email: "lea@exemple.fr", permissions: [], roles: [], groups: [], athlete, athlete_claim: null } as unknown as SessionUser;
}

function afficher(participation: Participation = RESULTAT) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ResultCardDownload participation={participation} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  getSession.mockReset();
  downloadResultCard.mockReset();
  downloadResultCard.mockResolvedValue(undefined);
  document.cookie = "tcn_logged_in=1; path=/";
});

describe("ResultCardDownload (#1371)", () => {
  it("offers the image to the account linked to this athlete, and downloads it", async () => {
    getSession.mockResolvedValue(session(LEA));
    afficher();

    await userEvent.click(await screen.findByRole("button", { name: "Télécharger l'image" }));

    await waitFor(() => expect(downloadResultCard).toHaveBeenCalledTimes(1));
    const [model, fileName] = downloadResultCard.mock.calls[0];
    expect(model).toMatchObject({ athlete: "Léa Martin", result: "2:10:05" });
    expect(fileName).toBe("resultat-triathlon-de-nantes.png");
  });

  it.each([
    ["an anonymous visitor", null, RESULTAT],
    ["an account linked to another athlete", { id: 7, prenom: "Autre", nom: "Fiche" }, RESULTAT],
    ["a pending result", LEA, { ...RESULTAT, is_pending_validation: true }],
    ["a relay", LEA, { ...RESULTAT, is_relay: true }],
  ])("offers nothing to %s", async (_, athlete, participation) => {
    getSession.mockResolvedValue(athlete === null ? null : session(athlete));
    afficher(participation as Participation);

    await waitFor(() => expect(getSession).toHaveBeenCalled());
    expect(screen.queryByRole("button", { name: "Télécharger l'image" })).not.toBeInTheDocument();
  });
});
