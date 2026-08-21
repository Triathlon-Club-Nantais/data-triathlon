import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import type { CourseBrief, SessionUser } from "@/lib/types";

const { listCourses, countCourses, setCourseReliability, getSession, rescrapeEventStream } =
  vi.hoisted(() => ({
    listCourses: vi.fn(),
    countCourses: vi.fn(),
    setCourseReliability: vi.fn(),
    getSession: vi.fn(),
    rescrapeEventStream: vi.fn(),
  }));

const push = vi.fn();

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: { listCourses, countCourses, setCourseReliability, getSession },
  };
});

vi.mock("@/lib/api/sse", () => ({ rescrapeEventStream }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
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

const AVEC_RESCRAPE: SessionUser = {
  ...AVEC_POUVOIR,
  permissions: ["quality:override", "courses:sources"],
} as SessionUser;

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

/** Même patron que `CourseSourcesPanel.test.tsx` : un flux SSE contrôlé à la
 * main, libéré au moment choisi par le test. */
function fluxControle(fin: object) {
  let liberer: () => void;
  const porte = new Promise<void>((resolve) => {
    liberer = resolve;
  });
  async function* generateur() {
    yield { phase: "saving", total: 10, imported: 2, updated: 1, skipped: 0, progress: 3 };
    await porte;
    yield fin;
  }
  return { generateur: generateur(), liberer: () => liberer() };
}

function rendre() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <QualityQueueTable />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  push.mockReset();
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

  it("« Marquer fiable » envoie le verdict favorable (AC4)", async () => {
    rendre();
    const ligne = (await screen.findByText("Triathlon de Vertou")).closest("tr")!;

    await userEvent.click(within(ligne).getByRole("button", { name: /^marquer fiable$/i }));
    const modale = await screen.findByRole("dialog");
    await userEvent.click(within(modale).getByRole("button", { name: /^marquer fiable$/i }));

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
    expect(screen.queryByRole("button", { name: /^marquer fiable$/i })).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /marquer douteuse/i }),
    ).not.toBeInTheDocument();
  });

  it("le filtre par anomalie restreint les lignes affichées", async () => {
    rendre();
    await screen.findByText("Triathlon de Vertou");

    await userEvent.click(screen.getByRole("combobox", { name: /anomalie/i }));
    await userEvent.click(await screen.findByRole("option", { name: "Trous dans le classement" }));

    expect(screen.getByText("Triathlon de Vertou")).toBeInTheDocument();
    expect(screen.queryByText("Triathlon de Carnac")).not.toBeInTheDocument();
  });

  it("distingue la file vide du filtre qui vide la page (AC…)", async () => {
    // Le filtre d'anomalie agit côté client, sur la page affichée (limite
    // assumée) : un code qui matchait sur la page 1 peut ne plus matcher sur
    // la page 2, sans que la file soit vide pour autant — deux messages
    // différents, pas le même.
    listCourses.mockImplementation((opts: { page?: number } = {}) =>
      Promise.resolve(opts.page === 2 ? [CARNAC] : [VERTOU, CARNAC]),
    );
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { rerender } = render(
      <QueryClientProvider client={client}>
        <QualityQueueTable />
      </QueryClientProvider>,
    );

    await screen.findByText("Triathlon de Vertou");
    await userEvent.click(screen.getByRole("combobox", { name: /anomalie/i }));
    await userEvent.click(await screen.findByRole("option", { name: "Trous dans le classement" }));
    expect(screen.getByText("Triathlon de Vertou")).toBeInTheDocument();
    expect(screen.queryByText("Triathlon de Carnac")).not.toBeInTheDocument();

    rerender(
      <QueryClientProvider client={client}>
        <QualityQueueTable page={2} />
      </QueryClientProvider>,
    );

    expect(
      await screen.findByText(/aucune épreuve ne porte cette anomalie sur cette page/i),
    ).toBeInTheDocument();
    expect(screen.queryByText(/aucune épreuve à revalider/i)).not.toBeInTheDocument();
  });

  it("annonce une file vide sans faire disparaître ses filtres", async () => {
    listCourses.mockResolvedValue([]);
    countCourses.mockResolvedValue({ total: 0 });
    rendre();

    expect(await screen.findByText(/aucune épreuve à revalider/i)).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: /anomalie/i })).toBeInTheDocument();
  });

  it("distingue la file vide d'un filtre par nom sans correspondance", async () => {
    listCourses.mockResolvedValue([]);
    countCourses.mockResolvedValue({ total: 0 });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <QualityQueueTable filtres={{ name: "vertou" }} />
      </QueryClientProvider>,
    );

    expect(await screen.findByText(/aucun résultat/i)).toBeInTheDocument();
    expect(screen.queryByText("Aucune épreuve à revalider")).not.toBeInTheDocument();
  });

  it("le filtre par date part dans la requête (#119)", async () => {
    rendre();
    await screen.findByText("Triathlon de Vertou");

    fireEvent.change(screen.getByLabelText(/^du$/i), { target: { value: "2026-05-01" } });
    await userEvent.click(screen.getByRole("button", { name: /^filtrer$/i }));

    expect(push).toHaveBeenCalledWith(
      expect.stringContaining("date_from=2026-05-01"),
    );
  });

  it("« Entrée » applique les filtres, sans attendre le clic (constat 7)", async () => {
    rendre();
    await screen.findByText("Triathlon de Vertou");

    await userEvent.type(screen.getByLabelText(/nom de l'épreuve/i), "Vertou{Enter}");

    expect(push).toHaveBeenCalledWith(expect.stringContaining("name=Vertou"));
  });

  it("« Réinitialiser », visible dès qu'un filtre est actif, le vide", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <QualityQueueTable filtres={{ name: "vertou" }} />
      </QueryClientProvider>,
    );
    await screen.findByText("Triathlon de Vertou");

    await userEvent.click(screen.getByRole("button", { name: /réinitialiser/i }));

    expect(push).toHaveBeenCalledWith("/admin/quality");
  });

  it("le re-scrape recharge la file en fin de flux, la ligne ne reste pas avec ses anciennes anomalies", async () => {
    getSession.mockResolvedValue(AVEC_RESCRAPE);
    const { generateur, liberer } = fluxControle({
      phase: "done", total: 10, imported: 1, updated: 9, skipped: 0,
      reconciled: 0, orphans_removed: 0,
    });
    rescrapeEventStream.mockReturnValue(generateur);
    const user = userEvent.setup();
    rendre();
    const ligne = (await screen.findByText("Triathlon de Vertou")).closest("tr")!;
    expect(listCourses).toHaveBeenCalledTimes(1);

    await user.click(within(ligne).getByRole("button", { name: /re-scraper/i }));
    liberer();

    await waitFor(() => expect(listCourses.mock.calls.length).toBeGreaterThan(1));
  });

  it("ne montre la progression que sur la ligne dont le re-scrape est en cours", async () => {
    getSession.mockResolvedValue(AVEC_RESCRAPE);
    const { generateur, liberer } = fluxControle({
      phase: "done", total: 10, imported: 1, updated: 9, skipped: 0,
      reconciled: 0, orphans_removed: 0,
    });
    rescrapeEventStream.mockReturnValue(generateur);
    const user = userEvent.setup();
    rendre();
    const ligneVertou = (await screen.findByText("Triathlon de Vertou")).closest("tr")!;
    const ligneCarnac = screen.getByText("Triathlon de Carnac").closest("tr")!;

    await user.click(within(ligneVertou).getByRole("button", { name: /re-scraper/i }));

    expect(
      await within(ligneVertou).findByRole("button", { name: /re-scrape en cours/i }),
    ).toBeInTheDocument();
    // L'autre ligne reste identifiable par son propre nom, sans revendiquer
    // « en cours » — et le hook n'étant pas multi-lignes, elle reste
    // désactivée le temps du flux (réserve documentée dans le rapport final).
    expect(
      within(ligneCarnac).getByRole("button", { name: /re-scraper triathlon de carnac/i }),
    ).toBeDisabled();

    liberer();
    await waitFor(() =>
      expect(
        within(ligneVertou).queryByRole("button", { name: /re-scrape en cours/i }),
      ).not.toBeInTheDocument(),
    );
  });

  it("annonce la progression du re-scrape dans une région live (constat 9)", async () => {
    getSession.mockResolvedValue(AVEC_RESCRAPE);
    const { generateur, liberer } = fluxControle({
      phase: "done", total: 10, imported: 1, updated: 9, skipped: 0,
      reconciled: 0, orphans_removed: 0,
    });
    rescrapeEventStream.mockReturnValue(generateur);
    const user = userEvent.setup();
    rendre();
    const ligne = (await screen.findByText("Triathlon de Vertou")).closest("tr")!;

    await user.click(within(ligne).getByRole("button", { name: /re-scraper/i }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      /re-scrape de triathlon de vertou.*3 sur 10 résultats/i,
    );

    liberer();
    await waitFor(() => expect(screen.queryByRole("status")).not.toBeInTheDocument());
  });
});
