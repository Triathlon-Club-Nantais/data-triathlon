import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { AthleteDetail, Participation, SessionUser } from "@/lib/types";

const { getSession, getAthlete } = vi.hoisted(() => ({ getSession: vi.fn(), getAthlete: vi.fn() }));
vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { ...original.apiClient, getSession, getAthlete } };
});
vi.mock("./OngletsMonEspace", () => ({
  OngletsMonEspace: ({ participations }: { participations: unknown[] }) => <div data-testid="onglets">{participations.length}</div>,
}));

vi.mock("./ColonneDroite", () => ({ ColonneDroite: () => <div data-testid="colonne-droite" /> }));

import { MonEspace } from "./MonEspace";

const LEA = { id: 42, prenom: "Léa", nom: "Martin" };
const session = (extra: Partial<SessionUser>) =>
  ({ id: 1, athlete: null, athlete_claim: null, permissions: [], roles: [], groups: [], ...extra }) as unknown as SessionUser;

let numero = 0;
function resultat(date: string, extra: Partial<Participation> = {}): Participation {
  numero += 1;
  return {
    id: numero, athlete: LEA,
    course: { id: numero, name: `E${numero}`, event_date: date, event_type: "triathlon-m", provider: "k", source_url: "", is_relay: false, is_reliable: true, distance_km: 10 },
    rank_overall: 20, course_finishers: 100, total_time: "1:00:00", status: "finisher", is_relay: false, is_pending_validation: false,
    ...extra,
  } as Participation;
}
const detail = (participations: Participation[]) => ({ athlete: LEA, participations, challenges: [] }) as unknown as AthleteDetail;

function afficher(seasons = [2026]) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MonEspace seasons={seasons} federalOnly />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  document.cookie = "tcn_logged_in=1; path=/";
});
afterEach(() => vi.useRealTimers());

describe("MonEspace access", () => {
  it("invites an anonymous visitor to log in", async () => {
    document.cookie = "tcn_logged_in=; path=/; max-age=0";
    afficher();

    expect(await screen.findByRole("link", { name: "Se connecter" })).toHaveAttribute("href", "/login");
    expect(getAthlete).not.toHaveBeenCalled();
  });

  it("invites a logged-in member without a linked athlete to claim a profile", async () => {
    getSession.mockResolvedValue(session({}));
    afficher();

    expect(await screen.findByRole("button", { name: /Trouvez votre fiche/ })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Se connecter" })).toBeNull();
    await waitFor(() => expect(getAthlete).not.toHaveBeenCalled());
  });

  it("says a pending claim is awaiting the club", async () => {
    getSession.mockResolvedValue(session({ athlete_claim: { id: 1, athlete: LEA, status: "pending", created_at: "" } }));
    afficher();

    expect(await screen.findByText(/demande de rattachement.*en attente/i)).toBeInTheDocument();
  });

  it("renders figures and both column slots for a linked member, comparing with the previous season to date", async () => {
    getSession.mockResolvedValue(session({ athlete: LEA }));
    vi.useFakeTimers({ toFake: ["Date"], now: new Date("2026-10-15T10:00:00Z") });
    getAthlete.mockImplementation(async (_id: number, filters: { seasons: string }) =>
      filters.seasons === "2025"
        ? detail([resultat("2025-10-01"), resultat("2025-11-20")])
        : detail([resultat("2026-09-20"), resultat("2026-10-01")]),
    );
    afficher();

    expect(await screen.findByTestId("mon-espace-centre")).toBeInTheDocument();
    expect(screen.getByTestId("mon-espace-droite")).toContainElement(screen.getByTestId("colonne-droite"));
    expect(screen.getByTestId("onglets")).toHaveTextContent("2");
    expect(getAthlete).toHaveBeenCalledWith(42, { seasons: "2026", federal_only: true });
    expect(getAthlete).toHaveBeenCalledWith(42, { seasons: "2025", federal_only: true });
    // The 2025-11-20 result is after the same date a year earlier and does not count: +1.
    await waitFor(() => expect(screen.getAllByTestId("ecart")[0]).toHaveTextContent("+1"));
    expect(screen.getByText("Épreuves").nextSibling).toHaveTextContent("2");
  });

  it("shows a friendly message and an instruction when the athlete cannot be loaded", async () => {
    getSession.mockResolvedValue(session({ athlete: LEA }));
    getAthlete.mockRejectedValue(new Error("boom 500 internal"));
    afficher();

    const alerte = await screen.findByRole("alert");
    expect(alerte).toHaveTextContent("Réessayez plus tard.");
    expect(alerte).not.toHaveTextContent("boom 500 internal");
  });

  it("does not compare when several seasons are selected", async () => {
    getSession.mockResolvedValue(session({ athlete: LEA }));
    getAthlete.mockResolvedValue(detail([resultat("2026-10-01")]));
    afficher([2026, 2025]);

    expect(await screen.findByTestId("mon-espace-centre")).toBeInTheDocument();
    expect(getAthlete).toHaveBeenCalledTimes(1);
    expect(screen.queryByTestId("ecart")).toBeNull();
  });

  it("still renders the tabs when the selected season has no club race (#1668)", async () => {
    getSession.mockResolvedValue(session({ athlete: LEA }));
    getAthlete.mockResolvedValue(detail([]));
    afficher();

    expect(await screen.findByTestId("onglets")).toHaveTextContent("0");
  });
});
