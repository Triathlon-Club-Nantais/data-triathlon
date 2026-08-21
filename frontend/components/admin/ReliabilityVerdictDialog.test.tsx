import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import type { CourseBrief } from "@/lib/types";

const { setCourseReliability } = vi.hoisted(() => ({ setCourseReliability: vi.fn() }));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { setCourseReliability } };
});

import { ReliabilityVerdictDialog } from "./ReliabilityVerdictDialog";

const EPREUVE: CourseBrief = {
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

function rendre(verdict: "fiable" | "douteuse" | "calcule") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const onOpenChange = vi.fn();
  render(
    <QueryClientProvider client={client}>
      <ReliabilityVerdictDialog course={EPREUVE} verdict={verdict} onOpenChange={onOpenChange} />
    </QueryClientProvider>,
  );
  return { onOpenChange };
}

beforeEach(() => {
  setCourseReliability.mockReset();
  setCourseReliability.mockResolvedValue({
    id: 7,
    is_reliable: true,
    is_reliable_computed: false,
    reliability_override: true,
    quality_issues: { rank_gap: 3 },
  });
});

describe("ReliabilityVerdictDialog", () => {
  it("envoie true et les notes saisies pour « Marquer fiable »", async () => {
    rendre("fiable");

    await userEvent.type(
      screen.getByLabelText(/motif/i),
      "Classement vérifié à la source.",
    );
    await userEvent.click(screen.getByRole("button", { name: /^marquer fiable$/i }));

    await waitFor(() =>
      expect(setCourseReliability).toHaveBeenCalledWith(7, {
        reliability_override: true,
        notes: "Classement vérifié à la source.",
      }),
    );
  });

  it("envoie false pour « Marquer douteuse »", async () => {
    rendre("douteuse");

    await userEvent.click(screen.getByRole("button", { name: /^marquer douteuse$/i }));

    await waitFor(() =>
      expect(setCourseReliability).toHaveBeenCalledWith(7, { reliability_override: false }),
    );
  });

  it("envoie null pour « Revenir à l'avis calculé »", async () => {
    rendre("calcule");

    await userEvent.click(screen.getByRole("button", { name: /revenir à l'avis calculé/i }));

    await waitFor(() =>
      expect(setCourseReliability).toHaveBeenCalledWith(7, { reliability_override: null }),
    );
  });

  it("rappelle les anomalies relevées, décodées", () => {
    rendre("fiable");

    expect(screen.getByText(/3 trous dans le classement/i)).toBeInTheDocument();
  });

  it("ferme après un envoi réussi", async () => {
    const { onOpenChange } = rendre("fiable");

    await userEvent.click(screen.getByRole("button", { name: /^marquer fiable$/i }));

    await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false));
  });

  it("un double-clic sur « Confirmer » ne déclenche qu'un seul envoi", async () => {
    // Résolution différée : sans elle, le premier envoi termine avant même le
    // second `fireEvent.click`, et le test ne prouverait rien sur la fenêtre
    // où `disabled` n'a pas encore pris effet.
    setCourseReliability.mockImplementation(
      () =>
        new Promise((resolve) =>
          setTimeout(
            () =>
              resolve({
                id: 7,
                is_reliable: true,
                is_reliable_computed: false,
                reliability_override: true,
                quality_issues: { rank_gap: 3 },
              }),
            10,
          ),
        ),
    );
    rendre("fiable");

    const bouton = screen.getByRole("button", { name: /^marquer fiable$/i });
    // `fireEvent`, pas `userEvent` : deux clics synchrones, enchaînés avant
    // que React n'ait eu la moindre chance de re-render `disabled`.
    fireEvent.click(bouton);
    fireEvent.click(bouton);

    await waitFor(() => expect(setCourseReliability).toHaveBeenCalledTimes(1));
  });
});
