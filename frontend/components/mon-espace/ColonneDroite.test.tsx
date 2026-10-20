import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Participation, SessionUser } from "@/lib/types";

const { getSession, getClubRosterRank, getAthlete, getMyTeammates, getEventsGeo } = vi.hoisted(() => ({
  getSession: vi.fn(), getClubRosterRank: vi.fn(), getAthlete: vi.fn(), getMyTeammates: vi.fn(), getEventsGeo: vi.fn(),
}));
vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { ...original.apiClient, getSession, getClubRosterRank, getAthlete, getMyTeammates, getEventsGeo } };
});

import { currentSeason } from "@/lib/utils/season";
import { ColonneDroite } from "./ColonneDroite";
import { DernierResultat } from "./DernierResultat";
import { MaPlaceAuClub } from "./MaPlaceAuClub";
import { ProchainPalier } from "./ProchainPalier";

const LEA = { id: 42, prenom: "Léa", nom: "Martin" };
const resultat = (extra: Partial<Participation> = {}) =>
  ({
    id: 7, athlete: LEA,
    course: { id: 3, name: "Triathlon de Nantes", event_date: "2026-10-01", event_type: "triathlon-m", is_relay: false },
    rank_overall: 12, course_finishers: 100, total_time: "2:01:02", is_relay: false, is_pending_validation: false,
    ...extra,
  }) as Participation;

function afficher(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

beforeEach(() => {
  vi.clearAllMocks();
  getMyTeammates.mockResolvedValue([]);
  getEventsGeo.mockResolvedValue([]);
  document.cookie = "tcn_logged_in=1; path=/";
  getSession.mockResolvedValue({ id: 1, athlete: LEA, permissions: [], roles: [], groups: [] } as unknown as SessionUser);
});

describe("ColonneDroite", () => {
  it("picks the latest result, flags its record and states the next milestone", async () => {
    const course = (id: number, name: string, event_date: string) => ({ id, name, event_date, event_type: "triathlon-m" }) as Participation["course"];
    const vieux = resultat({ id: 1, course: course(1, "Ancienne", "2025-05-01") });
    const autre = resultat({ id: 3, course: course(4, "Autre", "2025-06-01") });
    const recent = resultat({ id: 2, course: course(2, "Récente", "2026-10-01"), total_time: "1:50:00" });
    getAthlete.mockResolvedValue({ athlete: LEA, participations: [vieux, autre, recent], challenges: [] });
    getClubRosterRank.mockResolvedValue(null);
    afficher(<ColonneDroite athleteId={42} selection={[recent]} seasons={[currentSeason()]} federalOnly />);

    expect(await screen.findByRole("link", { name: /Récente/ })).toBeInTheDocument();
    expect(await screen.findByText("record perso")).toBeInTheDocument();
    expect(await screen.findByText(/Encore 1 épreuve pour égaler/)).toBeInTheDocument();
  });
});

describe("ColonneDroite past season", () => {
  it("states no next milestone for a season that is not the current one", async () => {
    const ancien = resultat({ id: 1, course: { id: 1, name: "Ancienne", event_date: "2024-05-01", event_type: "triathlon-m" } as Participation["course"] });
    const course = (id: number, event_date: string) => ({ id, name: "Passée", event_date, event_type: "triathlon-m" }) as Participation["course"];
    const passe = resultat({ id: 2, course: course(2, "2025-05-01") });
    const autres = [resultat({ id: 3, course: course(3, "2025-06-01") }), resultat({ id: 4, course: course(4, "2025-07-01") })];
    getAthlete.mockResolvedValue({ athlete: LEA, participations: [ancien, passe, ...autres], challenges: [] });
    getClubRosterRank.mockResolvedValue(null);
    afficher(<ColonneDroite athleteId={42} selection={[ancien]} seasons={[2024]} federalOnly />);

    expect(await screen.findByRole("link", { name: /Ancienne/ })).toBeInTheDocument();
    await vi.waitFor(() => expect(getAthlete).toHaveBeenCalled());
    await getAthlete.mock.results[0].value;
    await new Promise((r) => setTimeout(r, 20));
    expect(screen.queryByText(/Encore \d+ (épreuve|podium)/)).toBeNull();
  });
});

describe("ColonneDroite empty data", () => {
  it("shows the map card nowhere and the teammates card as empty", async () => {
    getAthlete.mockResolvedValue({ athlete: LEA, participations: [], challenges: [] });
    getClubRosterRank.mockResolvedValue(null);
    afficher(<ColonneDroite athleteId={42} selection={[resultat()]} seasons={[2026]} federalOnly />);

    expect(await screen.findByText(/Aucun coéquipier de course/)).toBeInTheDocument();
    expect(getEventsGeo).toHaveBeenCalled();
    expect(screen.queryByText("Carte de mes épreuves")).not.toBeInTheDocument();
  });
});

describe("ColonneDroite ties", () => {
  it("keeps the highest id when two results share the latest date", async () => {
    const course = (id: number, name: string) => ({ id, name, event_date: "2026-10-01", event_type: "triathlon-m" }) as Participation["course"];
    const premier = resultat({ id: 5, course: course(5, "Premiere") });
    const second = resultat({ id: 9, course: course(9, "Seconde") });
    getAthlete.mockResolvedValue({ athlete: LEA, participations: [], challenges: [] });
    getClubRosterRank.mockResolvedValue(null);
    afficher(<ColonneDroite athleteId={42} selection={[second, premier]} seasons={[2026]} federalOnly />);

    expect(await screen.findByRole("link", { name: /Seconde/ })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Premiere/ })).toBeNull();
  });
});

describe("DernierResultat", () => {
  it("shows the race, time, place, record badge, link and card button", async () => {
    afficher(<DernierResultat participation={resultat()} record />);

    expect(screen.getByRole("link", { name: /Triathlon de Nantes/ })).toHaveAttribute("href", "/courses/3/participations/7");
    expect(screen.getByText("2:01:02")).toBeInTheDocument();
    expect(screen.getByText(/12e/)).toBeInTheDocument();
    expect(screen.getByText("record perso")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Ma carte résultat" })).toBeInTheDocument();
  });

  it("has no badge when it is not a record and no card for a relay", async () => {
    afficher(<DernierResultat participation={resultat({ is_relay: true })} record={false} />);

    expect(screen.queryByText("record perso")).toBeNull();
    await screen.findByText(/Triathlon de Nantes/);
    expect(screen.queryByRole("button", { name: "Ma carte résultat" })).toBeNull();
  });

  it("offers no card for a result that is not the member's own", async () => {
    afficher(<DernierResultat participation={resultat({ athlete: { id: 99, prenom: "Zoé", nom: "Roux" } as Participation["athlete"] })} record={false} />);

    await screen.findByText(/Triathlon de Nantes/);
    await vi.waitFor(() => expect(getSession).toHaveBeenCalled());
    expect(screen.queryByRole("button", { name: "Ma carte résultat" })).toBeNull();
  });

  it("says there is no result yet", () => {
    afficher(<DernierResultat participation={null} record={false} />);
    expect(screen.getByText(/Aucun résultat sur cette sélection/)).toBeInTheDocument();
    expect(screen.getByText(/Changez de saison ou/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "ajoutez une épreuve" })).toHaveAttribute("href", "/ajouter");
  });
});

describe("MaPlaceAuClub", () => {
  it("shows the rank and its evolution against the previous season", async () => {
    getClubRosterRank.mockImplementation(async (_id: number, o: { seasons: number[] }) =>
      o.seasons[0] === 2025 ? { rank: 10, total: 80 } : { rank: 7, total: 90 },
    );
    afficher(<MaPlaceAuClub athleteId={42} seasons={[2026]} federalOnly />);

    expect(await screen.findByText("7e sur 90")).toBeInTheDocument();
    expect(await screen.findByText(/3 places gagnées/)).toBeInTheDocument();
  });

  it("shows no evolution on several seasons", async () => {
    getClubRosterRank.mockResolvedValue({ rank: 7, total: 90 });
    afficher(<MaPlaceAuClub athleteId={42} seasons={[2026, 2025]} federalOnly />);

    expect(await screen.findByText("7e sur 90")).toBeInTheDocument();
    expect(getClubRosterRank).toHaveBeenCalledTimes(1);
  });

  it("is hidden when the athlete has no rank", async () => {
    getClubRosterRank.mockResolvedValue(null);
    const { container } = afficher(<MaPlaceAuClub athleteId={42} seasons={[2026]} federalOnly />);

    await vi.waitFor(() => expect(getClubRosterRank).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });
});

describe("ProchainPalier", () => {
  it("states what is left to match the best season", () => {
    afficher(<ProchainPalier palier={{ type: "epreuves", reste: 2, cible: 12 }} />);
    expect(screen.getByText(/Encore 2 épreuves pour égaler votre meilleure saison/)).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "10");
    expect(screen.getByRole("progressbar")).toHaveStyle({ background: "var(--tcn-grey-300)" });
  });

  it("uses the singular and podiums", () => {
    afficher(<ProchainPalier palier={{ type: "podiums", reste: 1, cible: 3 }} />);
    expect(screen.getByText(/Encore 1 podium pour égaler/)).toBeInTheDocument();
  });

  it("is hidden without a milestone", () => {
    const { container } = afficher(<ProchainPalier palier={null} />);
    expect(container).toBeEmptyDOMElement();
  });
});
