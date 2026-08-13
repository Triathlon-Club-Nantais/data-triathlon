import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiError } from "@/lib/api/client";
import type { Feedback } from "@/lib/types";

const { listFeedback } = vi.hoisted(() => ({
  listFeedback: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: { listFeedback },
  };
});

import { FeedbackTable } from "./FeedbackTable";

const SIGNALEMENT: Feedback = {
  id: 1,
  type: "bug",
  title: "Le classement n'affiche pas mon temps",
  body: "Après l'import, mon temps total reste vide.",
  page_url: "https://tcn.example/courses/123",
  user_agent: "Mozilla/5.0",
  status: "nouveau",
  github_url: null,
  created_at: "2026-08-01T14:54:28Z",
  email: null,
};

function afficher() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <FeedbackTable />
    </QueryClientProvider>,
  );
}

describe("FeedbackTable", () => {
  beforeEach(() => {
    listFeedback.mockReset();
    listFeedback.mockResolvedValue([SIGNALEMENT]);
  });

  it("affiche les colonnes date, type, titre et statut", async () => {
    afficher();

    expect(await screen.findByText(SIGNALEMENT.title)).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /date/i })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /^type/i })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /titre/i })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /statut/i })).toBeInTheDocument();
  });

  it("interroge created_at desc par défaut", async () => {
    afficher();

    await waitFor(() => expect(listFeedback).toHaveBeenCalledWith("created_at", "desc"));
  });

  it("change le tri au clic sur un en-tête", async () => {
    afficher();
    await screen.findByText(SIGNALEMENT.title);
    listFeedback.mockClear();

    fireEvent.click(screen.getByRole("button", { name: /^type/i }));

    await waitFor(() => expect(listFeedback).toHaveBeenCalledWith("type", "desc"));
  });

  it("inverse l'ordre sur un second clic de la même colonne", async () => {
    afficher();
    await screen.findByText(SIGNALEMENT.title);

    fireEvent.click(screen.getByRole("button", { name: /date/i }));
    await waitFor(() => expect(listFeedback).toHaveBeenCalledWith("created_at", "asc"));
  });

  it("dit « aucun retour utilisateur » sur une liste vide", async () => {
    listFeedback.mockResolvedValue([]);

    afficher();

    expect(await screen.findByText(/aucun retour utilisateur/i)).toBeInTheDocument();
  });

  it("dit « accès refusé » sur un 403", async () => {
    listFeedback.mockRejectedValue(new ApiError(403, "Refusé"));

    afficher();

    expect(await screen.findByText(/accès refusé/i)).toBeInTheDocument();
  });
});
