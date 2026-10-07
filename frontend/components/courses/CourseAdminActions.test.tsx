import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import type { CourseBrief, SessionUser } from "@/lib/types";

const api = vi.hoisted(() => ({
  getSession: vi.fn(),
  listCourses: vi.fn(),
  getCourseSummary: vi.fn(),
  getCourseDeletionImpact: vi.fn(),
  deleteCourse: vi.fn(),
  getCourseMergeImpact: vi.fn(),
  mergeCourses: vi.fn(),
  updateCourse: vi.fn(),
  setCourseReliability: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: api };
});

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

// Témoin du chargement paresseux : le panneau ne doit être importé que pour qui a un pouvoir.
const panelLoaded = vi.hoisted(() => vi.fn());
vi.mock("./CourseAdminPanel", async (importOriginal) => {
  panelLoaded();
  return importOriginal();
});

const { refresh, push } = vi.hoisted(() => ({ refresh: vi.fn(), push: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh, push }) }));

import { CourseAdminActions } from "./CourseAdminActions";

const BAYMAN: CourseBrief = {
  id: 1047,
  name: "Bayman 2024 L",
  event_date: "2024-09-14",
  event_type: "triathlon-l",
  provider: "klikego",
  source_url: "https://klikego.com/bayman",
  is_relay: false,
  is_reliable: false,
  quality_issues: null,
};

const JUMELLE: CourseBrief = {
  ...BAYMAN,
  id: 1162,
  event_date: "2024-09-15",
  provider: "breizhchrono",
  source_url: "https://breizhchrono.com/bayman",
};

function session(permissions: string[]): SessionUser {
  return {
    id: 1,
    email: "admin@exemple.fr",
    permissions,
    roles: [],
    created_at: "2026-01-01T00:00:00Z",
  } as unknown as SessionUser;
}

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <CourseAdminActions course={BAYMAN} total={420} tcnCount={2} />
    </QueryClientProvider>,
  );
}

const BOUTONS = {
  corriger: /corriger l'épreuve/i,
  supprimer: /^supprimer l'épreuve$/i,
  avis: /avis de fiabilité/i,
  fusionner: /fusionner avec une autre épreuve/i,
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe("CourseAdminActions", () => {
  it("ne rend rien pour un visiteur anonyme", async () => {
    api.getSession.mockResolvedValue(null);
    const { container } = afficher();
    await waitFor(() => expect(api.getSession).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
    expect(panelLoaded).not.toHaveBeenCalled();
  });

  it.each([
    [["courses:write"], ["corriger"]],
    [["courses:delete"], ["supprimer"]],
    [["quality:override"], ["avis"]],
    [["courses:sources"], []],
    [["courses:delete", "courses:sources"], ["supprimer", "fusionner"]],
  ] as const)("avec %j, ne propose que %j", async (permissions, attendus) => {
    api.getSession.mockResolvedValue(session([...permissions]));
    afficher();
    await waitFor(() => expect(api.getSession).toHaveBeenCalled());
    // Les présents d'abord : les absences ne se lisent qu'une fois le panneau
    // chargé (import dynamique, lent sur une machine chargée).
    const entrees = Object.entries(BOUTONS);
    for (const [cle, nom] of entrees) {
      if ((attendus as readonly string[]).includes(cle)) {
        expect(await screen.findByRole("button", { name: nom }, { timeout: 3000 })).toBeInTheDocument();
      }
    }
    for (const [cle, nom] of entrees) {
      if (!(attendus as readonly string[]).includes(cle)) {
        expect(screen.queryByRole("button", { name: nom })).not.toBeInTheDocument();
      }
    }
  });

  it("corriger rafraîchit la page une fois l'épreuve enregistrée", async () => {
    api.getSession.mockResolvedValue(session(["courses:write"]));
    api.updateCourse.mockResolvedValue(BAYMAN);
    const user = userEvent.setup();
    afficher();

    await user.click(await screen.findByRole("button", { name: BOUTONS.corriger }, { timeout: 3000 }));
    await user.click(await screen.findByRole("button", { name: /enregistrer/i }));

    await waitFor(() => expect(refresh).toHaveBeenCalled());
    expect(api.updateCourse).toHaveBeenCalledWith(1047, expect.objectContaining({ name: BAYMAN.name }));
  });

  it("supprimer renvoie vers les résultats, la fiche n'existant plus", async () => {
    api.getSession.mockResolvedValue(session(["courses:delete"]));
    api.getCourseDeletionImpact.mockResolvedValue({ course_id: 1047, name: BAYMAN.name, participations: 420, athletes: 3 });
    api.deleteCourse.mockResolvedValue(null);
    const user = userEvent.setup();
    afficher();

    await user.click(await screen.findByRole("button", { name: BOUTONS.supprimer }, { timeout: 3000 }));
    const confirmer = await screen.findByRole("button", { name: /supprimer définitivement/i });
    await waitFor(() => expect(confirmer).toBeEnabled());
    await user.click(confirmer);

    await waitFor(() => expect(push).toHaveBeenCalledWith("/resultats"));
    expect(api.deleteCourse).toHaveBeenCalledWith(1047);
  });

  it("l'avis de fiabilité ouvre le verdict choisi et rafraîchit après décision", async () => {
    api.getSession.mockResolvedValue(session(["quality:override"]));
    api.setCourseReliability.mockResolvedValue({});
    const user = userEvent.setup();
    afficher();

    await user.click(await screen.findByRole("button", { name: BOUTONS.avis }, { timeout: 3000 }));
    await user.click(await screen.findByRole("menuitem", { name: /marquer fiable/i }));
    await user.click(await screen.findByRole("button", { name: /^marquer fiable$/i }));

    await waitFor(() => expect(refresh).toHaveBeenCalled());
    expect(api.setCourseReliability).toHaveBeenCalledWith(1047, { reliability_override: true });
  });

  it("fusionne avec une épreuve d'une autre date trouvée par la recherche, puis suit l'épreuve conservée", async () => {
    api.getSession.mockResolvedValue(session(["courses:delete", "courses:sources"]));
    api.listCourses.mockResolvedValue([BAYMAN, JUMELLE]);
    api.getCourseSummary.mockResolvedValue({ total: 430, tcn_count: 5 });
    api.getCourseMergeImpact.mockResolvedValue({
      target: { id: 1162, name: JUMELLE.name, event_date: "2024-09-15", event_type: "triathlon-l", is_relay: false, provider: "breizhchrono", participations: 430 },
      absorbed: { id: 1047, name: BAYMAN.name, event_date: "2024-09-14", event_type: "triathlon-l", is_relay: false, provider: "klikego", participations: 420 },
      participations_without_match: 0,
      tcn_participations_without_match: 0,
      athletes_orphaned: 0,
      same_source_url: false,
    });
    api.mergeCourses.mockResolvedValue({ participations_deleted: 420, athletes_purged: 0 });
    const user = userEvent.setup();
    afficher();

    await user.click(await screen.findByRole("button", { name: BOUTONS.fusionner }, { timeout: 3000 }));
    await user.type(screen.getByRole("searchbox"), "Bayman");

    // L'épreuve consultée n'est pas proposée : on ne la fusionne pas avec elle-même.
    // Recherche temporisée de 300 ms : délai élargi pour une machine chargée.
    const candidat = await screen.findByRole("button", { name: /n° 1162/ }, { timeout: 3000 });
    expect(screen.queryByRole("button", { name: /n° 1047/ })).not.toBeInTheDocument();
    expect(api.listCourses).toHaveBeenCalledWith(expect.objectContaining({ name: "Bayman" }));
    expect(screen.getByRole("status")).toHaveTextContent("1 épreuve trouvée.");

    await user.click(candidat);

    // La jumelle porte plus de résultats TCN : elle est proposée d'office comme cible.
    await waitFor(() => expect(api.getCourseMergeImpact).toHaveBeenCalledWith(1162, 1047));
    const fusionner = await screen.findByRole("button", { name: /^fusionner$/i });
    await waitFor(() => expect(fusionner).toBeEnabled());
    await user.click(fusionner);

    await waitFor(() => expect(push).toHaveBeenCalledWith("/courses/1162"));
    expect(api.mergeCourses).toHaveBeenCalledWith(1162, 1047);
  });

  it("cherche par numéro quand la saisie est un identifiant", async () => {
    api.getSession.mockResolvedValue(session(["courses:delete", "courses:sources"]));
    api.listCourses.mockResolvedValue([JUMELLE]);
    const user = userEvent.setup();
    afficher();

    await user.click(await screen.findByRole("button", { name: BOUTONS.fusionner }, { timeout: 3000 }));
    await user.type(screen.getByRole("searchbox"), "1162");

    await screen.findByRole("button", { name: /n° 1162/ }, { timeout: 3000 });
    expect(api.listCourses).toHaveBeenCalledWith(expect.objectContaining({ id: "1162" }));
  });

  it("annonce l'échec de la recherche", async () => {
    api.getSession.mockResolvedValue(session(["courses:delete", "courses:sources"]));
    api.listCourses.mockRejectedValue(new Error("boom"));
    const user = userEvent.setup();
    afficher();

    await user.click(await screen.findByRole("button", { name: BOUTONS.fusionner }, { timeout: 3000 }));
    await user.type(screen.getByRole("searchbox"), "Bayman");

    expect(
      await screen.findByText("La recherche n'a pas abouti. Réessayez.", {}, { timeout: 3000 }),
    ).toBeInTheDocument();
  });

  it("occupe le candidat choisi pendant la lecture de son résumé, puis affiche l'échec", async () => {
    api.getSession.mockResolvedValue(session(["courses:delete", "courses:sources"]));
    api.listCourses.mockResolvedValue([JUMELLE]);
    let rejeter: (error: Error) => void = () => {};
    api.getCourseSummary.mockReturnValue(new Promise((_, reject) => (rejeter = reject)));
    const user = userEvent.setup();
    afficher();

    await user.click(await screen.findByRole("button", { name: BOUTONS.fusionner }, { timeout: 3000 }));
    await user.type(screen.getByRole("searchbox"), "1162");
    const candidat = await screen.findByRole("button", { name: /n° 1162/ }, { timeout: 3000 });
    await user.click(candidat);

    expect(candidat).toHaveAttribute("aria-busy", "true");
    expect(candidat).toBeDisabled();

    rejeter(new Error("Épreuve introuvable"));
    expect(await screen.findByRole("alert")).toHaveTextContent("Épreuve introuvable");
    expect(candidat).not.toHaveAttribute("aria-busy", "true");
    expect(candidat).toBeEnabled();
  });
});
