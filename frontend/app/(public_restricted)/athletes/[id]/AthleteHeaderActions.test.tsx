import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { SessionUser } from "@/lib/types";
import { AthleteHeaderActions } from "./AthleteHeaderActions";

const { getSession, requestAthleteClaim } = vi.hoisted(() => ({
  getSession: vi.fn(),
  requestAthleteClaim: vi.fn(),
}));
vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { ...original.apiClient, getSession, requestAthleteClaim } };
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
  // #1582 : le panneau se charge à la demande ; la sélection ne doit pas
  // redescendre en secondaire avant que « Corriger la fiche » soit là. Premier
  // test du bloc : une fois le module en cache, l'état transitoire n'existe plus.
  it("bascule la hiérarchie d'un seul rendu, panneau chargé", async () => {
    getSession.mockResolvedValue(session(["athletes:write"]));
    const intermediaire = vi.fn();
    const observer = new MutationObserver(() => {
      const selection = screen.queryByRole("button", { name: /choisir cet athlète/i });
      if (
        selection?.classList.contains("tcn-btn--secondary") &&
        !screen.queryByRole("button", { name: /corriger la fiche/i })
      )
        intermediaire();
    });
    observer.observe(document.body, { subtree: true, childList: true, attributes: true });
    afficher();

    await screen.findByRole("button", { name: /corriger la fiche/i });
    observer.disconnect();
    expect(intermediaire).not.toHaveBeenCalled();
  });

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

describe("AthleteHeaderActions, rattachement de la fiche (#1325)", () => {
  const JEAN = { id: 12, prenom: "Jean", nom: "Dupont" };
  const AUTRE = { id: 99, prenom: "Marie", nom: "Gaudin" };

  function avec(extra: Partial<SessionUser>): SessionUser {
    return { ...session([]), athlete: null, athlete_claim: null, ...extra };
  }

  it("propose « C'est moi » à un connecté sans rattachement, et envoie la demande", async () => {
    getSession.mockResolvedValue(avec({}));
    requestAthleteClaim.mockResolvedValue({});
    afficher();

    await screen.findByRole("button", { name: /c'est moi/i });
    expect(screen.queryByRole("link", { name: /me comparer/i })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /c'est moi/i }));

    expect(requestAthleteClaim).toHaveBeenCalledWith(12);
    expect(screen.getByText(/le club valide/i)).toBeInTheDocument();
  });

  it("dit qu'une demande sur cette fiche est en attente, sans la reproposer", async () => {
    getSession.mockResolvedValue(
      avec({ athlete_claim: { id: 1, athlete: JEAN, status: "pending", created_at: "2026-10-17T10:00:00Z" } }),
    );
    afficher();

    expect(await screen.findByText(/demande de rattachement en attente/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /c'est moi/i })).not.toBeInTheDocument();
  });

  it("marque la fiche du compte rattaché, sans rien à choisir ni à demander", async () => {
    getSession.mockResolvedValue(avec({ athlete: JEAN }));
    afficher();

    expect(await screen.findByText(/votre fiche/i)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /me comparer/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /choisir cet athlète/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /c'est moi/i })).not.toBeInTheDocument();
  });

  it("ne propose ni de choisir ni de demander une autre fiche à un compte rattaché", async () => {
    getSession.mockResolvedValue(avec({ athlete: AUTRE }));
    afficher();

    await screen.findByText((_, el) => el?.tagName === "P" && el.textContent === "Fiche de votre compte : Marie Gaudin");
    expect(screen.getByRole("link", { name: "Marie Gaudin" })).toHaveAttribute("href", "/athletes/99");
    // #1675 : sa propre fiche s'ouvre avec ce coéquipier déjà choisi (`?comparer=`, #1701).
    expect(screen.getByRole("link", { name: "Me comparer à Jean Dupont" })).toHaveAttribute(
      "href",
      "/athletes/99?comparer=12",
    );
    expect(screen.queryByRole("button", { name: /choisir cet athlète/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /c'est moi/i })).not.toBeInTheDocument();
  });

  it("ne propose rien à un anonyme", async () => {
    getSession.mockResolvedValue(null);
    afficher();

    await screen.findByRole("button", { name: /choisir cet athlète/i });
    expect(screen.queryByRole("button", { name: /c'est moi/i })).not.toBeInTheDocument();
  });
});
