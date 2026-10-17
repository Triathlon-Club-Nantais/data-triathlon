import { readFileSync } from "node:fs";
import { join } from "node:path";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { SessionUser } from "@/lib/types";

const { getSession, loaded } = vi.hoisted(() => ({ getSession: vi.fn(), loaded: new Set<string>() }));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { ...original.apiClient, getSession } };
});

// Each factory runs only when the module is actually imported: `loaded` tells
// which panels a visitor's browser would have downloaded.
vi.mock("./AthleteOppositionAction", () => {
  loaded.add("AthleteOppositionAction");
  return { AthleteOppositionAction: () => <p>opposition</p> };
});
vi.mock("./ParticipationAdminActions", () => {
  loaded.add("ParticipationAdminActions");
  return { ParticipationAdminActions: () => <p>gestes résultat</p> };
});


const ATHLETE = { id: 12, prenom: "Jean", nom: "Dupont", club: null };
const RESULT = { id: 3, athleteId: 12, coureur: "Jean Dupont", epreuve: "Tri de Nantes" } as never;

function session(permissions: string[]): SessionUser {
  return { id: 1, email: "a@exemple.fr", display_name: "a", permissions, roles: [] } as unknown as SessionUser;
}

// Modules remis à zéro à chaque test : sans quoi une fabrique déjà exécutée ne
// signalerait plus son chargement et le test négatif passerait à vide.
async function afficher() {
  vi.resetModules();
  const { AthleteOppositionAction, ParticipationAdminActions } = await import("./AdminGates");
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <AthleteOppositionAction athlete={ATHLETE} />
      <ParticipationAdminActions resultat={RESULT} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  loaded.clear();
  document.cookie = "tcn_logged_in=1; path=/";
});

describe("athlete admin gates (#1582)", () => {
  it("never loads the admin panels for a visitor without power", async () => {
    getSession.mockResolvedValue(session([]));
    await afficher();
    await waitFor(() => expect(getSession).toHaveBeenCalled());
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(loaded.size).toBe(0);
    expect(screen.queryByText("opposition")).toBeNull();
  });

  it("loads and renders each panel once the session carries its power", async () => {
    getSession.mockResolvedValue(session(["oppositions:manage", "participations:delete"]));
    await afficher();
    expect(await screen.findByText("opposition")).toBeInTheDocument();
    expect(await screen.findByText("gestes résultat")).toBeInTheDocument();
  });

  it("keeps the seven admin panels out of the athlete route's static imports", () => {
    const route = join(__dirname, "../../app/(public_restricted)/athletes/[id]");
    const panels =
      /from\s+["']@\/components\/athletes\/(AthleteAdminPanel|AthleteOppositionAction|ParticipationAdminActions|AthleteDetachAction|SeasonValidationPanel|VolunteerActionsList|AthleteVariantsPanel)["']/;
    for (const file of ["page.tsx", "AthleteHeaderActions.tsx", "EventsTable.tsx"]) {
      const source = readFileSync(join(route, file), "utf8").replace(/import\s+type[^;]+;/g, "");
      expect(source, file).not.toMatch(panels);
    }
  });
});
