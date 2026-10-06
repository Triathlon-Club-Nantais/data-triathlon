import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiError } from "@/lib/api/client";
import type { CourseMergeImpact, DuplicateCourse } from "@/lib/types";

const { getCourseMergeImpact, mergeCourses, toastError, toastSuccess } = vi.hoisted(() => ({
  getCourseMergeImpact: vi.fn(),
  mergeCourses: vi.fn(),
  toastError: vi.fn(),
  toastSuccess: vi.fn(),
}));

vi.mock("sonner", () => ({ toast: { error: toastError, success: toastSuccess } }));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { getCourseMergeImpact, mergeCourses } };
});

import { MergeCoursesDialog } from "./MergeCoursesDialog";

const KLIKEGO: DuplicateCourse = {
  id: 38,
  name: "Triathlon et SwimRun Mesquer-Quimiac 2026",
  event_date: "2026-06-13",
  event_type: "swimrun-s",
  is_relay: false,
  provider: "klikego",
  source_url: "https://klikego.com/x",
  total: 185,
  tcn_count: 3,
  created_at: "2026-06-14T08:00:00",
};

const BREIZHCHRONO: DuplicateCourse = {
  id: 50,
  name: "Triathlon et SwimRun Mesquer-Quimiac 2026",
  event_date: "2026-06-13",
  event_type: "triathlon-s",
  is_relay: false,
  provider: "breizhchrono",
  source_url: "https://breizhchrono.com/x",
  total: 179,
  tcn_count: 3,
  created_at: "2026-06-14T08:00:00",
};

const IMPACT: CourseMergeImpact = {
  target: { id: 38, name: KLIKEGO.name, event_date: "2026-06-13", event_type: "swimrun-s", is_relay: false, provider: "klikego", participations: 185 },
  absorbed: { id: 50, name: BREIZHCHRONO.name, event_date: "2026-06-13", event_type: "triathlon-s", is_relay: false, provider: "breizhchrono", participations: 179 },
  participations_without_match: 12,
  tcn_participations_without_match: 1,
  athletes_orphaned: 4,
  same_source_url: false,
};

function afficher(open = true) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MergeCoursesDialog courseA={KLIKEGO} courseB={BREIZHCHRONO} open={open} onOpenChange={() => {}} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("MergeCoursesDialog", () => {
  it("affiche les deux épreuves sans aperçu, bouton de fusion inerte avant toute sélection", async () => {
    afficher();

    expect(await screen.findByText(/klikego/i)).toBeInTheDocument();
    expect(screen.getByText(/breizh chrono/i)).toBeInTheDocument();
    expect(getCourseMergeImpact).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: /^fusionner$/i })).toBeDisabled();
  });

  describe("Couëron 2025 : la republication runnerbreizh ne porte aucun club (#1199)", () => {
    const RUNNERBREIZH: DuplicateCourse = {
      ...KLIKEGO, id: 718, provider: "runnerbreizh", total: 270, tcn_count: 0,
    };
    const TIMEPULSE: DuplicateCourse = {
      ...BREIZHCHRONO, id: 1016, provider: "timepulse", total: 310, tcn_count: 28,
    };

    function afficherCoueron() {
      const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
      return render(
        <QueryClientProvider client={client}>
          <MergeCoursesDialog courseA={RUNNERBREIZH} courseB={TIMEPULSE} open onOpenChange={() => {}} />
        </QueryClientProvider>,
      );
    }

    it("propose d'office de garder l'épreuve qui porte les résultats TCN", async () => {
      getCourseMergeImpact.mockResolvedValue(IMPACT);
      afficherCoueron();

      expect(await screen.findByRole("button", { name: /garder.*timepulse/i })).toHaveAttribute(
        "aria-pressed",
        "true",
      );
      await waitFor(() => expect(getCourseMergeImpact).toHaveBeenCalledWith(1016, 718));
    });

    it("avertit quand l'épreuve absorbée porte plus de résultats TCN que la cible", async () => {
      getCourseMergeImpact.mockResolvedValue(IMPACT);
      const user = userEvent.setup();
      afficherCoueron();

      await user.click(await screen.findByRole("button", { name: /garder.*runner/i }));

      expect(await screen.findByRole("alert")).toHaveTextContent(
        /l'épreuve supprimée porte 28 résultats TCN, celle conservée 0/i,
      );
    });
  });

  it("choisir une cible déclenche l'aperçu avec l'autre épreuve comme absorbée", async () => {
    getCourseMergeImpact.mockResolvedValue(IMPACT);
    const user = userEvent.setup();
    afficher();

    await user.click(await screen.findByRole("button", { name: /garder.*klikego/i }));

    await waitFor(() => expect(getCourseMergeImpact).toHaveBeenCalledWith(38, 50));
  });

  it("annonce les participations sans correspondance et les fiches purgées", async () => {
    getCourseMergeImpact.mockResolvedValue(IMPACT);
    const user = userEvent.setup();
    afficher();

    await user.click(await screen.findByRole("button", { name: /garder.*klikego/i }));

    // Chercheurs sur le texte intégral du <li> (récursif) : les nombres seuls
    // (« 1 », « 4 ») apparaissent aussi dans les dates et totaux affichés par
    // les cartes d'épreuve, donc un `getByText` par regex simple serait ambigu.
    await waitFor(() =>
      expect(
        screen.getByText(
          (_, el) => el?.tagName === "LI" && /disparaîtront \(dont 1 du TCN\)/.test(el.textContent ?? ""),
        ),
      ).toBeInTheDocument(),
    );
    expect(
      screen.getByText((_, el) => el?.tagName === "LI" && /^4 fiches? athlète/.test(el.textContent ?? "")),
    ).toBeInTheDocument();
  });

  it("accorde le singulier à un seul résultat et une seule fiche orpheline", async () => {
    getCourseMergeImpact.mockResolvedValue({
      ...IMPACT,
      participations_without_match: 1,
      tcn_participations_without_match: 1,
      athletes_orphaned: 1,
    });
    const user = userEvent.setup();
    afficher();

    await user.click(await screen.findByRole("button", { name: /garder.*klikego/i }));

    await waitFor(() =>
      expect(
        screen.getByText(
          (_, el) =>
            el?.tagName === "LI" &&
            /^1 résultat de l'épreuve absorbée n'a pas d'équivalent côté cible et disparaîtra/.test(
              el.textContent ?? "",
            ),
        ),
      ).toBeInTheDocument(),
    );
    expect(
      screen.getByText(
        (_, el) =>
          el?.tagName === "LI" &&
          /^1 fiche athlète ne conservera plus aucun résultat et sera retirée/.test(
            el.textContent ?? "",
          ),
      ),
    ).toBeInTheDocument();
  });

  it("accorde le singulier à zéro résultat et zéro fiche orpheline (#1142)", async () => {
    getCourseMergeImpact.mockResolvedValue({
      ...IMPACT,
      participations_without_match: 0,
      tcn_participations_without_match: 0,
      athletes_orphaned: 0,
    });
    const user = userEvent.setup();
    afficher();

    await user.click(await screen.findByRole("button", { name: /garder.*klikego/i }));

    await waitFor(() =>
      expect(
        screen.getByText(
          (_, el) =>
            el?.tagName === "LI" &&
            /^0 résultat de l'épreuve absorbée n'a pas d'équivalent côté cible et disparaîtra/.test(
              el.textContent ?? "",
            ),
        ),
      ).toBeInTheDocument(),
    );
    expect(
      screen.getByText(
        (_, el) =>
          el?.tagName === "LI" &&
          /^0 fiche athlète ne conservera plus aucun résultat et sera retirée/.test(
            el.textContent ?? "",
          ),
      ),
    ).toBeInTheDocument();
  });

  it("fusionne après confirmation et notifie le succès", async () => {
    getCourseMergeImpact.mockResolvedValue(IMPACT);
    mergeCourses.mockResolvedValue({
      target_id: 38,
      absorbed_id: 50,
      participations_deleted: 179,
      athletes_purged: 4,
      source_added: true,
      sources: [],
    });
    const user = userEvent.setup();
    afficher();

    await user.click(await screen.findByRole("button", { name: /garder.*klikego/i }));
    await user.click(await screen.findByRole("button", { name: /^fusionner$/i }));

    await waitFor(() => expect(mergeCourses).toHaveBeenCalledWith(38, 50));
    expect(toastSuccess).toHaveBeenCalledWith(
      "« Triathlon et SwimRun Mesquer-Quimiac 2026 » a été fusionnée dans la source conservée — " +
        "179 résultats sans correspondance ont disparu, 4 fiches athlète purgées.",
    );
  });

  it.each([
    [0, "0 résultat sans correspondance a disparu, 0 fiche athlète purgée."],
    [1, "1 résultat sans correspondance a disparu, 1 fiche athlète purgée."],
    [2, "2 résultats sans correspondance ont disparu, 2 fiches athlète purgées."],
  ])("accorde le bilan de la fusion à %i (#1142)", async (n, bilan) => {
    getCourseMergeImpact.mockResolvedValue(IMPACT);
    mergeCourses.mockResolvedValue({
      target_id: 38,
      absorbed_id: 50,
      participations_deleted: n,
      athletes_purged: n,
      source_added: true,
      sources: [],
    });
    const user = userEvent.setup();
    afficher();

    await user.click(await screen.findByRole("button", { name: /garder.*klikego/i }));
    await user.click(await screen.findByRole("button", { name: /^fusionner$/i }));

    await waitFor(() =>
      expect(toastSuccess).toHaveBeenCalledWith(
        `« Triathlon et SwimRun Mesquer-Quimiac 2026 » a été fusionnée dans la source conservée — ${bilan}`,
      ),
    );
  });

  it("notifie l'échec sans fermer la modale", async () => {
    getCourseMergeImpact.mockResolvedValue(IMPACT);
    mergeCourses.mockRejectedValue(new ApiError(400, "Une épreuve ne peut pas être fusionnée avec elle-même."));
    const user = userEvent.setup();
    afficher();

    await user.click(await screen.findByRole("button", { name: /garder.*klikego/i }));
    await user.click(await screen.findByRole("button", { name: /^fusionner$/i }));

    await waitFor(() =>
      expect(toastError).toHaveBeenCalledWith("Une épreuve ne peut pas être fusionnée avec elle-même."),
    );
    expect(await screen.findByRole("button", { name: /^fusionner$/i })).toBeInTheDocument();
  });

  it("n'active pas la fusion tant que l'aperçu n'a pas répondu", async () => {
    getCourseMergeImpact.mockImplementation(() => new Promise(() => {}));
    const user = userEvent.setup();
    afficher();

    await user.click(await screen.findByRole("button", { name: /garder.*klikego/i }));

    expect(screen.getByRole("button", { name: /^fusionner$/i })).toBeDisabled();
  });
});
