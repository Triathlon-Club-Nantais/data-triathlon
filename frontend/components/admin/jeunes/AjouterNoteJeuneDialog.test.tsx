import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

const { addProfileLogEntry } = vi.hoisted(() => ({ addProfileLogEntry: vi.fn() }));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { addProfileLogEntry } };
});

import { AjouterNoteJeuneDialog } from "./AjouterNoteJeuneDialog";

function afficher(onOpenChange = vi.fn()) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return {
    onOpenChange,
    ...render(
      <QueryClientProvider client={client}>
        <AjouterNoteJeuneDialog
          profileId={42}
          jeuneNom="Alix Martin"
          open
          onOpenChange={onOpenChange}
        />
      </QueryClientProvider>,
    ),
  };
}

describe("AjouterNoteJeuneDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("nomme le jeune dans le titre", () => {
    afficher();

    expect(screen.getByText(/alix martin/i)).toBeInTheDocument();
  });

  it("délègue au journal de bord existant (#867)", async () => {
    addProfileLogEntry.mockResolvedValue({});
    const { onOpenChange } = afficher();

    await userEvent.type(screen.getByLabelText(/^note$/i), "A progressé sur le crawl.");
    await userEvent.click(screen.getByRole("button", { name: /enregistrer/i }));

    expect(addProfileLogEntry).toHaveBeenCalledWith(
      42,
      "A progressé sur le crawl.",
      expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/),
    );
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("date la note du jour local de l'encadrant, pas de celui du serveur", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(2026, 8, 24, 0, 30));
    addProfileLogEntry.mockResolvedValue({});
    afficher();

    await userEvent.type(screen.getByLabelText(/^note$/i), "Séance de nuit.");
    await userEvent.click(screen.getByRole("button", { name: /enregistrer/i }));

    expect(addProfileLogEntry).toHaveBeenCalledWith(42, "Séance de nuit.", "2026-09-24");
  });

  it("n'enregistre pas une note vide", async () => {
    afficher();

    expect(screen.getByRole("button", { name: /enregistrer/i })).toBeDisabled();
  });
});
