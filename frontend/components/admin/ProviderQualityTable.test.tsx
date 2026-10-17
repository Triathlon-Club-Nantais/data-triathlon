import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiError } from "@/lib/api/client";

const { getProviderQuality } = vi.hoisted(() => ({ getProviderQuality: vi.fn() }));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { getProviderQuality } };
});

import { ProviderQualityTable } from "./ProviderQualityTable";

function afficher() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <ProviderQualityTable />
    </QueryClientProvider>,
  );
}

beforeEach(() => vi.clearAllMocks());

describe("ProviderQualityTable", () => {
  it("rend une ligne par fournisseur et une colonne par anomalie présente", async () => {
    getProviderQuality.mockResolvedValue([
      { provider: "klikego", course_count: 120, unreliable_count: 7, anomalies: { rank_gap: 5, duplicate_bib: 2 } },
      { provider: "wiclax", course_count: 40, unreliable_count: 0, anomalies: {} },
    ]);
    afficher();

    const table = await screen.findByRole("table");
    const entetes = within(table).getAllByRole("columnheader").map((th) => th.textContent);
    expect(entetes).toEqual([
      "Fournisseur",
      "Épreuves",
      "Non fiables",
      "Trous dans le classement",
      "Dossards en doublon",
    ]);
    const [, klikego, wiclax] = within(table).getAllByRole("row");
    expect(within(klikego).getByRole("rowheader")).toHaveTextContent("Klikego");
    expect(within(klikego).getAllByRole("cell").map((td) => td.textContent)).toEqual([
      "120", "7", "5", "2",
    ]);
    expect(within(wiclax).getByRole("rowheader")).toHaveTextContent("Wiclax");
    expect(within(wiclax).getAllByRole("cell").map((td) => td.textContent)).toEqual([
      "40", "0", "0", "0",
    ]);
  });

  it("dit qu'aucune épreuve importée n'a de fournisseur sur une base vide", async () => {
    getProviderQuality.mockResolvedValue([]);
    afficher();

    expect(await screen.findByText("Aucune épreuve importée depuis un fournisseur")).toBeInTheDocument();
  });

  it("dit le refus plutôt qu'un tableau vide", async () => {
    getProviderQuality.mockRejectedValue(new ApiError(403, "Forbidden"));
    afficher();

    expect(await screen.findByText(/pouvoir/i)).toBeInTheDocument();
    expect(screen.queryByRole("table")).toBeNull();
  });
});
