import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiError } from "@/lib/api/client";
import { DangerConfirmProvider } from "@/components/admin/DangerConfirm";
import { confirmerDansLeDialog } from "@/components/admin/__tests__/dangerConfirm";
import type { DuplicateCandidateList, SessionUser } from "@/lib/types";

const { listCourseDuplicates, getSession, ignoreCourseDuplicate, toastError, toastSuccess } =
  vi.hoisted(() => ({
    listCourseDuplicates: vi.fn(),
    getSession: vi.fn(),
    ignoreCourseDuplicate: vi.fn(),
    toastError: vi.fn(),
    toastSuccess: vi.fn(),
  }));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: { listCourseDuplicates, getSession, ignoreCourseDuplicate },
  };
});

vi.mock("sonner", () => ({ toast: { error: toastError, success: toastSuccess } }));

import { CourseDuplicatesTable } from "./CourseDuplicatesTable";

const AVEC_DROIT: SessionUser = {
  id: 1,
  email: "admin@exemple.fr",
  permissions: ["courses:sources", "courses:delete"],
  roles: [],
  created_at: "2026-01-01T00:00:00Z",
} as unknown as SessionUser;

const SANS_SUPPRESSION: SessionUser = { ...AVEC_DROIT, permissions: ["courses:sources"] } as SessionUser;

const PAIRE: DuplicateCandidateList = {
  candidates: [
    {
      reason: "shared_event_id",
      reason_label: "Identifiant d'événement partagé",
      courses: [
        {
          id: 38, name: "Triathlon et SwimRun Mesquer-Quimiac 2026", event_date: "2026-06-13",
          event_type: "swimrun-s", is_relay: false, provider: "klikego",
          source_url: "https://klikego.com/x", total: 185, tcn_count: 3,
        },
        {
          id: 50, name: "Triathlon et SwimRun Mesquer-Quimiac 2026", event_date: "2026-06-13",
          event_type: "triathlon-s", is_relay: false, provider: "breizhchrono",
          source_url: "https://breizhchrono.com/x", total: 179, tcn_count: 3,
        },
      ],
    },
  ],
};

const MEME_URL: DuplicateCandidateList = {
  candidates: [
    {
      reason: "same_source_url",
      reason_label: "Même URL de source",
      courses: [
        {
          id: 38, name: "Mesquer", event_date: "2026-06-13", event_type: "swimrun-s",
          is_relay: false, provider: "klikego", source_url: "https://klikego.com/x",
          total: 185, tcn_count: 3,
        },
        {
          id: 39, name: "Mesquer", event_date: "2026-06-13", event_type: "triathlon-s",
          is_relay: false, provider: "klikego", source_url: "https://klikego.com/x",
          total: 60, tcn_count: 0,
        },
      ],
    },
  ],
};

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <DangerConfirmProvider>
        <CourseDuplicatesTable />
      </DangerConfirmProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("CourseDuplicatesTable", () => {
  it("dit qu'il n'y a aucun doublon suspect sur une liste vide", async () => {
    getSession.mockResolvedValue(AVEC_DROIT);
    listCourseDuplicates.mockResolvedValue({ candidates: [] });

    afficher();

    expect(await screen.findByText(/aucun doublon suspect/i)).toBeInTheDocument();
  });

  it("affiche la raison et les deux épreuves de chaque paire", async () => {
    getSession.mockResolvedValue(AVEC_DROIT);
    listCourseDuplicates.mockResolvedValue(PAIRE);

    afficher();

    expect(await screen.findByText(/identifiant d'événement partagé/i)).toBeInTheDocument();
    expect(screen.getByText(/klikego/i)).toBeInTheDocument();
    expect(screen.getByText(/breizh chrono/i)).toBeInTheDocument();
  });

  it("propose la fusion à un porteur de courses:delete", async () => {
    getSession.mockResolvedValue(AVEC_DROIT);
    listCourseDuplicates.mockResolvedValue(PAIRE);

    afficher();

    expect(await screen.findByRole("button", { name: /fusionner/i })).toBeInTheDocument();
  });

  it("peint le déclencheur de fusion en rouge — la fusion est sans retour", async () => {
    getSession.mockResolvedValue(AVEC_DROIT);
    listCourseDuplicates.mockResolvedValue(PAIRE);

    afficher();

    // `aria-invalid:*` porte "destructive" sur tout bouton quel que soit son
    // variant — c'est `bg-destructive`, propre au variant, qui distingue
    // vraiment (piège connu, #499).
    expect((await screen.findByRole("button", { name: /fusionner/i })).className).toContain(
      "bg-destructive",
    );
  });

  it("ne propose aucune fusion sans courses:delete", async () => {
    getSession.mockResolvedValue(SANS_SUPPRESSION);
    listCourseDuplicates.mockResolvedValue(PAIRE);

    afficher();

    await screen.findByText(/identifiant d'événement partagé/i);
    expect(screen.queryByRole("button", { name: /fusionner/i })).not.toBeInTheDocument();
  });

  it("signale qu'une même URL se corrige plutôt qu'elle ne se fusionne", async () => {
    getSession.mockResolvedValue(AVEC_DROIT);
    listCourseDuplicates.mockResolvedValue(MEME_URL);

    afficher();

    expect(await screen.findByText(/même url de source/i)).toBeInTheDocument();
    expect(screen.getByText(/correction du type d'épreuve/i)).toBeInTheDocument();
  });

  it("dit « accès refusé » sur un 403, et non « aucun doublon »", async () => {
    getSession.mockResolvedValue(AVEC_DROIT);
    listCourseDuplicates.mockRejectedValue(new ApiError(403, "Refusé"));

    afficher();

    expect(await screen.findByText(/accès refusé/i)).toBeInTheDocument();
    expect(screen.queryByText(/aucun doublon suspect/i)).not.toBeInTheDocument();
  });

  // --- Écarter une paire (#754) -----------------------------------------------

  it("propose d'écarter à un porteur du seul courses:sources, sans courses:delete", async () => {
    getSession.mockResolvedValue(SANS_SUPPRESSION);
    listCourseDuplicates.mockResolvedValue(PAIRE);

    afficher();

    expect(await screen.findByRole("button", { name: /écarter/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /fusionner/i })).not.toBeInTheDocument();
  });

  it("ne peint pas le bouton « Écarter » en destructif — le geste ne supprime rien", async () => {
    getSession.mockResolvedValue(AVEC_DROIT);
    listCourseDuplicates.mockResolvedValue(PAIRE);

    afficher();

    expect(
      (await screen.findByRole("button", { name: /écarter/i })).className,
    ).not.toContain("bg-destructive");
  });

  it("demande confirmation avant d'écarter — le geste n'a pas d'écran retour (#754)", async () => {
    const user = userEvent.setup();
    getSession.mockResolvedValue(AVEC_DROIT);
    listCourseDuplicates.mockResolvedValue(PAIRE);

    afficher();
    await user.click(await screen.findByRole("button", { name: /écarter/i }));

    expect(await screen.findByText("Écarter cette paire ?")).toBeInTheDocument();
    expect(ignoreCourseDuplicate).not.toHaveBeenCalled();
  });

  it("renoncer dans le dialog n'écarte rien", async () => {
    const user = userEvent.setup();
    getSession.mockResolvedValue(AVEC_DROIT);
    listCourseDuplicates.mockResolvedValue(PAIRE);

    afficher();
    await user.click(await screen.findByRole("button", { name: /écarter/i }));
    await user.click(await screen.findByRole("button", { name: "Renoncer" }));

    expect(ignoreCourseDuplicate).not.toHaveBeenCalled();
  });

  it("écarte la paire une fois la confirmation donnée, et confirme par un toast", async () => {
    const user = userEvent.setup();
    getSession.mockResolvedValue(AVEC_DROIT);
    listCourseDuplicates.mockResolvedValue(PAIRE);
    ignoreCourseDuplicate.mockResolvedValue({
      course_id_a: 38,
      course_id_b: 50,
      ignored_at: "2026-08-30T12:00:00Z",
    });

    afficher();
    await user.click(await screen.findByRole("button", { name: /écarter/i }));
    await confirmerDansLeDialog("Écarter");

    expect(ignoreCourseDuplicate).toHaveBeenCalledWith(38, 50);
    await vi.waitFor(() => expect(toastSuccess).toHaveBeenCalled());
    expect(toastError).not.toHaveBeenCalled();
  });

  it("affiche le message du refus si l'écart échoue", async () => {
    const user = userEvent.setup();
    getSession.mockResolvedValue(AVEC_DROIT);
    listCourseDuplicates.mockResolvedValue(PAIRE);
    ignoreCourseDuplicate.mockRejectedValue(new ApiError(409, "Cette paire d'épreuves est déjà écartée."));

    afficher();
    await user.click(await screen.findByRole("button", { name: /écarter/i }));
    await confirmerDansLeDialog("Écarter");

    await vi.waitFor(() =>
      expect(toastError).toHaveBeenCalledWith("Cette paire d'épreuves est déjà écartée."),
    );
  });
});
