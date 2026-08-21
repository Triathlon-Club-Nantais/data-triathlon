import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import type { CourseBrief, SessionUser } from "@/lib/types";

const { listCourses, countCourses, setCourseReliability, getSession } = vi.hoisted(() => ({
  listCourses: vi.fn(),
  countCourses: vi.fn(),
  setCourseReliability: vi.fn(),
  getSession: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: { listCourses, countCourses, setCourseReliability, getSession },
  };
});

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => "/admin/quality",
}));

import { QualityQueueTable } from "./QualityQueueTable";

const AVEC_POUVOIR: SessionUser = {
  id: 1,
  email: "validateur@exemple.fr",
  permissions: ["quality:override"],
  roles: [],
  created_at: "2026-01-01T00:00:00Z",
} as unknown as SessionUser;

const SANS_POUVOIR: SessionUser = { ...AVEC_POUVOIR, permissions: [] } as SessionUser;

const VERTOU: CourseBrief = {
  id: 7,
  name: "Triathlon de Vertou",
  event_date: "2026-06-13",
  event_type: "triathlon-s",
  provider: "klikego",
  source_url: "https://klikego.com/x",
  is_relay: false,
  is_reliable: false,
  quality_issues: { rank_gap: 3 },
};

const CARNAC: CourseBrief = {
  ...VERTOU,
  id: 8,
  name: "Triathlon de Carnac",
  event_date: "2026-05-02",
  quality_issues: { duplicate_bib: 2 },
};

function rendre() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <QualityQueueTable />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  listCourses.mockReset();
  countCourses.mockReset();
  setCourseReliability.mockReset();
  getSession.mockReset();
  listCourses.mockResolvedValue([VERTOU, CARNAC]);
  countCourses.mockResolvedValue({ total: 2 });
  getSession.mockResolvedValue(AVEC_POUVOIR);
  setCourseReliability.mockResolvedValue({
    id: 7,
    is_reliable: true,
    is_reliable_computed: false,
    reliability_override: true,
    quality_issues: { rank_gap: 3 },
  });
});

describe("QualityQueueTable", () => {
  it("ne demande que les épreuves à revalider", async () => {
    rendre();

    await waitFor(() =>
      expect(listCourses).toHaveBeenCalledWith(
        expect.objectContaining({ unreliable: true }),
      ),
    );
  });

  it("affiche les anomalies de chaque épreuve en libellés lisibles (AC2)", async () => {
    rendre();

    expect(await screen.findByText(/3 trous dans le classement/i)).toBeInTheDocument();
    expect(screen.getByText(/2 dossards en doublon/i)).toBeInTheDocument();
  });

  it("« Marquer OK » envoie le verdict favorable (AC4)", async () => {
    rendre();
    const ligne = (await screen.findByText("Triathlon de Vertou")).closest("tr")!;

    await userEvent.click(within(ligne).getByRole("button", { name: /marquer ok/i }));
    await userEvent.click(await screen.findByRole("button", { name: /confirmer/i }));

    await waitFor(() =>
      expect(setCourseReliability).toHaveBeenCalledWith(
        7,
        expect.objectContaining({ reliability_override: true }),
      ),
    );
  });

  it("n'offre aucun geste de verdict sans le pouvoir", async () => {
    getSession.mockResolvedValue(SANS_POUVOIR);
    rendre();

    await screen.findByText("Triathlon de Vertou");
    expect(screen.queryByRole("button", { name: /marquer ok/i })).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /marquer douteuse/i }),
    ).not.toBeInTheDocument();
  });

  it("le filtre par anomalie restreint les lignes affichées", async () => {
    rendre();
    await screen.findByText("Triathlon de Vertou");

    await userEvent.selectOptions(
      screen.getByLabelText(/anomalie/i),
      "rank_gap",
    );

    expect(screen.getByText("Triathlon de Vertou")).toBeInTheDocument();
    expect(screen.queryByText("Triathlon de Carnac")).not.toBeInTheDocument();
  });

  it("annonce une file vide sans faire disparaître ses filtres", async () => {
    listCourses.mockResolvedValue([]);
    countCourses.mockResolvedValue({ total: 0 });
    rendre();

    expect(await screen.findByText(/aucune épreuve à revalider/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/anomalie/i)).toBeInTheDocument();
  });
});
