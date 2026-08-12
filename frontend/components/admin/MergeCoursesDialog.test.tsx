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
  it("affiche les deux épreuves sans aperçu ni bouton de fusion avant toute sélection", async () => {
    afficher();

    expect(await screen.findByText(/klikego/i)).toBeInTheDocument();
    expect(screen.getByText(/breizh chrono/i)).toBeInTheDocument();
    expect(getCourseMergeImpact).not.toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: /^fusionner$/i })).not.toBeInTheDocument();
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
      screen.getByText((_, el) => el?.tagName === "LI" && /^4 fiches? coureur/.test(el.textContent ?? "")),
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
    await waitFor(() => expect(toastSuccess).toHaveBeenCalled());
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

  it("ne propose aucune fusion tant que l'aperçu n'a pas répondu", async () => {
    getCourseMergeImpact.mockImplementation(() => new Promise(() => {}));
    const user = userEvent.setup();
    afficher();

    await user.click(await screen.findByRole("button", { name: /garder.*klikego/i }));

    expect(screen.queryByRole("button", { name: /^fusionner$/i })).not.toBeInTheDocument();
  });
});
