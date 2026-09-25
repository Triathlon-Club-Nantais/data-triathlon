import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

const { updateTrainingSession } = vi.hoisted(() => ({ updateTrainingSession: vi.fn() }));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { updateTrainingSession } };
});

import { NoteSeanceForm } from "./NoteSeanceForm";

function afficher(props: Partial<React.ComponentProps<typeof NoteSeanceForm>> = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <NoteSeanceForm sessionId={1} note="" peutEcrire {...props} />
    </QueryClientProvider>,
  );
}

describe("NoteSeanceForm", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("affiche la note existante", () => {
    afficher({ note: "Bassin partagé." });

    expect(screen.getByDisplayValue("Bassin partagé.")).toBeInTheDocument();
  });

  it("enregistre la note saisie", async () => {
    updateTrainingSession.mockResolvedValue({});

    afficher();
    await userEvent.type(screen.getByLabelText(/note de séance/i), "Bassin partagé.");
    await userEvent.click(screen.getByRole("button", { name: /enregistrer/i }));

    expect(updateTrainingSession).toHaveBeenCalledWith(1, { note: "Bassin partagé." });
  });

  it("n'enregistre pas une soumission vide", async () => {
    afficher();

    // Le bouton est désactivé tant que le champ est vide : rien à cliquer,
    // et une soumission clavier ne déclenche donc pas la mutation.
    expect(screen.getByRole("button", { name: /enregistrer/i })).toBeDisabled();
    expect(updateTrainingSession).not.toHaveBeenCalled();
  });

  it("n'enregistre pas une soumission uniquement faite d'espaces", async () => {
    afficher();

    await userEvent.type(screen.getByLabelText(/note de séance/i), "   ");

    expect(screen.getByRole("button", { name: /enregistrer/i })).toBeDisabled();
  });

  it("efface une note déjà enregistrée", async () => {
    updateTrainingSession.mockResolvedValue({});

    afficher({ note: "Mauvaise séance." });
    await userEvent.clear(screen.getByLabelText(/note de séance/i));
    await userEvent.click(screen.getByRole("button", { name: /enregistrer/i }));

    expect(updateTrainingSession).toHaveBeenCalledWith(1, { note: "" });
  });

  it("n'affiche aucun contrôle d'écriture sans jeunes:write", () => {
    afficher({ peutEcrire: false, note: "Bassin partagé." });

    expect(screen.queryByLabelText(/note de séance/i)).not.toBeInTheDocument();
    expect(screen.getByText("Bassin partagé.")).toBeInTheDocument();
  });

  it("n'affiche rien sans note existante ni pouvoir d'écriture", () => {
    const { container } = afficher({ peutEcrire: false, note: "" });

    expect(container).toBeEmptyDOMElement();
  });
});
