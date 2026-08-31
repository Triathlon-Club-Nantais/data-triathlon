import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { SessionUser } from "@/lib/types";
import { AthleteHeaderActions } from "./AthleteHeaderActions";

const { getSession } = vi.hoisted(() => ({ getSession: vi.fn() }));
vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { ...original.apiClient, getSession } };
});

vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: vi.fn() }) }));

const ATHLETE = { id: 12, prenom: "Jean", nom: "Dupont", club: "Triathlon Club Nantais" };

const BENEFICE = /retrouver ses résultats en un geste/i;

function session(permissions: string[]): SessionUser {
  return {
    id: 1,
    email: "admin@exemple.fr",
    display_name: "admin",
    created_at: "2026-01-01T00:00:00Z",
    permissions,
    roles: [],
  } as unknown as SessionUser;
}

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <AthleteHeaderActions athlete={ATHLETE} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  const stock = new Map<string, string>();
  Object.defineProperty(window, "localStorage", {
    configurable: true,
    value: {
      getItem: (cle: string) => stock.get(cle) ?? null,
      setItem: (cle: string, valeur: string) => void stock.set(cle, valeur),
      removeItem: (cle: string) => void stock.delete(cle),
      clear: () => stock.clear(),
    },
  });
  document.cookie = "tcn_logged_in=1; path=/";
});

// #753 — audit UI/UX : la hiérarchie devient conditionnelle au pouvoir du
// visiteur. Sans `athletes:write`, rien ne change par rapport à avant.
describe("AthleteHeaderActions — sans athletes:write", () => {
  it("garde la sélection primaire, seule commande rendue", async () => {
    getSession.mockResolvedValue(session([]));
    afficher();

    const bouton = await screen.findByRole("button", { name: /choisir cet athlète/i });
    expect(bouton).toHaveClass("tcn-btn--primary");
    expect(screen.queryByRole("button", { name: /corriger la fiche/i })).not.toBeInTheDocument();
  });
});

describe("AthleteHeaderActions — avec athletes:write", () => {
  it("place « Corriger la fiche » en tête, en primaire", async () => {
    getSession.mockResolvedValue(session(["athletes:write"]));
    afficher();

    await screen.findByRole("button", { name: /corriger la fiche/i });
    const boutons = screen.getAllByRole("button");
    expect(boutons[0]).toHaveAccessibleName(/corriger la fiche/i);
    expect(boutons[0]).toHaveClass("tcn-btn--primary");
  });

  it("relègue la sélection en secondaire", async () => {
    getSession.mockResolvedValue(session(["athletes:write"]));
    afficher();

    await screen.findByRole("button", { name: /corriger la fiche/i });
    const selection = screen.getByRole("button", { name: /choisir cet athlète/i });
    expect(selection).toHaveClass("tcn-btn--secondary");
  });

  it("garde le bénéfice de la sélection affiché malgré la relégation", async () => {
    getSession.mockResolvedValue(session(["athletes:write"]));
    afficher();

    await screen.findByRole("button", { name: /corriger la fiche/i });
    expect(screen.getByText(BENEFICE)).toBeInTheDocument();
  });
});
