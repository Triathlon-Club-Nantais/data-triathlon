import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { AdminVolunteerActionOut, SessionUser } from "@/lib/types";
import { VolunteerActionsList } from "./VolunteerActionsList";

const { getSession, listValidatedVolunteerActions } = vi.hoisted(() => ({
  getSession: vi.fn(),
  listValidatedVolunteerActions: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { ...original.apiClient, getSession, listValidatedVolunteerActions } };
});

function session(permissions: string[]): SessionUser {
  return {
    id: 7,
    email: "admin@exemple.fr",
    display_name: "admin",
    created_at: "2026-01-01T00:00:00Z",
    permissions,
    roles: [],
  } as unknown as SessionUser;
}

const VALIDEE: AdminVolunteerActionOut = {
  id: 1,
  athlete_id: 42,
  season: 2025,
  title: "Ravitaillement",
  description: "Poste eau km 15.",
  status: "validee",
  declared_by_user_id: 7,
  created_at: "2026-08-28T13:00:00Z",
};

const SANS_TITRE: AdminVolunteerActionOut = {
  id: 2,
  athlete_id: 42,
  season: 2024,
  title: null,
  description: null,
  status: "validee",
  declared_by_user_id: 3,
  created_at: "2025-06-01T13:00:00Z",
};

function afficher() {
  document.cookie = "tcn_logged_in=1; path=/";
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <VolunteerActionsList athleteId={42} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("VolunteerActionsList", () => {
  it("ne rend rien pour un connecté sans le pouvoir dédié", async () => {
    getSession.mockResolvedValue(session([]));

    const { container } = afficher();

    await waitFor(() => expect(getSession).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
    expect(listValidatedVolunteerActions).not.toHaveBeenCalled();
  });

  it("affiche titre et description des actions validées pour un titulaire du pouvoir", async () => {
    getSession.mockResolvedValue(session(["athletes:volunteer_validate"]));
    listValidatedVolunteerActions.mockResolvedValue([VALIDEE]);

    afficher();

    expect(await screen.findByText("Ravitaillement")).toBeInTheDocument();
    expect(screen.getByText("Poste eau km 15.")).toBeInTheDocument();
  });

  it("affiche un repli d'affichage pour une ligne sans titre ni description", async () => {
    getSession.mockResolvedValue(session(["athletes:volunteer_validate"]));
    listValidatedVolunteerActions.mockResolvedValue([SANS_TITRE]);

    afficher();

    await waitFor(() => expect(screen.getAllByText("—").length).toBeGreaterThanOrEqual(2));
  });

  it("affiche un état vide explicite quand l'athlète n'a aucune action validée", async () => {
    getSession.mockResolvedValue(session(["athletes:volunteer_validate"]));
    listValidatedVolunteerActions.mockResolvedValue([]);

    afficher();

    expect(await screen.findByText(/aucune action de bénévolat validée/i)).toBeInTheDocument();
  });

  it("affiche un squelette de chargement plutôt qu'un espace vide muet", async () => {
    getSession.mockResolvedValue(session(["athletes:volunteer_validate"]));
    listValidatedVolunteerActions.mockReturnValue(new Promise(() => {}));

    afficher();

    expect(await screen.findByTestId("volunteer-actions-skeleton")).toBeInTheDocument();
  });

  it("distingue un échec de chargement d'une liste vide", async () => {
    getSession.mockResolvedValue(session(["athletes:volunteer_validate"]));
    listValidatedVolunteerActions.mockRejectedValue(new Error("Boum"));

    afficher();

    expect(await screen.findByText(/n'ont pas pu être charg/i)).toBeInTheDocument();
    expect(screen.queryByText(/aucune action de bénévolat validée/i)).not.toBeInTheDocument();
  });
});
