import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { SessionUser, VolunteerAction } from "@/lib/types";
import { SeasonValidationPanel } from "./SeasonValidationPanel";

const { getSession, declareVolunteerAction, getSeasonQuota, validateSeason, unvalidateSeason } =
  vi.hoisted(() => ({
    getSession: vi.fn(),
    declareVolunteerAction: vi.fn(),
    getSeasonQuota: vi.fn(),
    validateSeason: vi.fn(),
    unvalidateSeason: vi.fn(),
  }));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: {
      getSession,
      declareVolunteerAction,
      getSeasonQuota,
      validateSeason,
      unvalidateSeason,
    },
  };
});

const { toastSuccess, toastError } = vi.hoisted(() => ({
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}));
vi.mock("sonner", () => ({ toast: { success: toastSuccess, error: toastError } }));

const ATHLETE = { id: 42, nom: "Lemée", prenom: "Jean-Marc" };

const ACTION: VolunteerAction = {
  id: 1,
  athlete_id: 42,
  season: 2025,
  declared_by_user_id: 7,
  created_at: "2026-08-28T13:00:00Z",
};

function session(permissions: string[]): SessionUser {
  return {
    id: 7,
    email: "benevole@exemple.fr",
    display_name: "benevole",
    created_at: "2026-01-01T00:00:00Z",
    permissions,
    roles: [],
  } as unknown as SessionUser;
}

function afficher() {
  document.cookie = "tcn_logged_in=1; path=/";
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <SeasonValidationPanel athlete={ATHLETE} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("SeasonValidationPanel — déclarer un bénévolat (US2)", () => {
  it("ne rend rien pour un connecté sans le pouvoir dédié", async () => {
    getSession.mockResolvedValue(session([]));

    const { container } = afficher();

    await waitFor(() => expect(getSession).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it("offre l'action à un titulaire du pouvoir dédié", async () => {
    getSession.mockResolvedValue(session(["athletes:volunteer_manage"]));

    afficher();

    expect(
      await screen.findByRole("button", { name: /déclarer une action de bénévolat/i }),
    ).toBeInTheDocument();
  });

  it("déclare un bénévolat pour la saison en cours au clic", async () => {
    getSession.mockResolvedValue(session(["athletes:volunteer_manage"]));
    declareVolunteerAction.mockResolvedValue(ACTION);

    afficher();
    const bouton = await screen.findByRole("button", { name: /déclarer une action de bénévolat/i });
    await userEvent.click(bouton);

    await waitFor(() => expect(declareVolunteerAction).toHaveBeenCalledWith(42, expect.any(Number)));
    expect(toastSuccess).toHaveBeenCalled();
  });

  it("affiche un message d'échec si la déclaration échoue", async () => {
    getSession.mockResolvedValue(session(["athletes:volunteer_manage"]));
    declareVolunteerAction.mockRejectedValue(new Error("Boum"));

    afficher();
    const bouton = await screen.findByRole("button", { name: /déclarer une action de bénévolat/i });
    await userEvent.click(bouton);

    await waitFor(() => expect(toastError).toHaveBeenCalled());
  });
});

describe("SeasonValidationPanel — valider la saison (US3, FR-009 à FR-013)", () => {
  it("n'offre pas la validation à un titulaire du seul pouvoir de bénévolat", async () => {
    getSession.mockResolvedValue(session(["athletes:volunteer_manage"]));

    afficher();
    await screen.findByRole("button", { name: /déclarer une action de bénévolat/i });

    expect(screen.queryByRole("button", { name: /^valider la saison$/i })).not.toBeInTheDocument();
  });

  it("affiche l'indicateur de quota et le bouton Valider quand le quota n'est pas atteint (FR-012)", async () => {
    getSession.mockResolvedValue(session(["athletes:season_validate"]));
    getSeasonQuota.mockResolvedValue({
      validated_count: 2,
      has_volunteer_action: false,
      season_validated: false,
    });

    afficher();

    expect(await screen.findByText(/2\/3 épreuves validées/i)).toBeInTheDocument();
    expect(screen.getByText(/bénévolat non déclaré/i)).toBeInTheDocument();
    const bouton = screen.getByRole("button", { name: /^valider la saison$/i });
    expect(bouton).not.toBeDisabled();
  });

  it("valide la saison au clic, sans bloquer même si le quota n'est pas atteint", async () => {
    getSession.mockResolvedValue(session(["athletes:season_validate"]));
    getSeasonQuota.mockResolvedValue({
      validated_count: 1,
      has_volunteer_action: false,
      season_validated: false,
    });
    validateSeason.mockResolvedValue({});

    afficher();
    const bouton = await screen.findByRole("button", { name: /^valider la saison$/i });
    await userEvent.click(bouton);

    await waitFor(() => expect(validateSeason).toHaveBeenCalledWith(42, expect.any(Number)));
    expect(toastSuccess).toHaveBeenCalled();
  });

  it("affiche Dévalider quand la saison est déjà validée, et dévalide au clic", async () => {
    getSession.mockResolvedValue(session(["athletes:season_validate"]));
    getSeasonQuota.mockResolvedValue({
      validated_count: 3,
      has_volunteer_action: true,
      season_validated: true,
    });
    unvalidateSeason.mockResolvedValue(undefined);

    afficher();
    const bouton = await screen.findByRole("button", { name: /^dévalider la saison$/i });
    await userEvent.click(bouton);

    await waitFor(() => expect(unvalidateSeason).toHaveBeenCalledWith(42, expect.any(Number)));
    expect(toastSuccess).toHaveBeenCalled();
  });
});
