import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";

const { submitFeedback } = vi.hoisted(() => ({ submitFeedback: vi.fn() }));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { submitFeedback } };
});

import { FeedbackButton } from "./FeedbackButton";

describe("FeedbackButton", () => {
  it("le bouton flottant est visible", () => {
    render(<FeedbackButton />);

    expect(screen.getByRole("button", { name: /signaler un bug/i })).toBeInTheDocument();
  });

  it("bloque la soumission si le titre et la description sont vides", async () => {
    const user = userEvent.setup();
    render(<FeedbackButton />);

    await user.click(screen.getByRole("button", { name: /signaler un bug/i }));
    await user.click(screen.getByRole("button", { name: "Envoyer" }));

    expect(screen.getByText(/obligatoires/i)).toBeInTheDocument();
    expect(submitFeedback).not.toHaveBeenCalled();
  });

  it("affiche une confirmation après envoi", async () => {
    submitFeedback.mockResolvedValue({ id: 1, status: "nouveau" });
    const user = userEvent.setup();
    render(<FeedbackButton />);

    await user.click(screen.getByRole("button", { name: /signaler un bug/i }));
    await user.type(screen.getByLabelText("Titre"), "Un titre");
    await user.type(screen.getByLabelText("Description"), "Une description.");
    await user.click(screen.getByRole("button", { name: "Envoyer" }));

    await waitFor(() => {
      expect(screen.getByText(/bien été envoyé/i)).toBeInTheDocument();
    });
    expect(submitFeedback).toHaveBeenCalledWith(
      expect.objectContaining({ type: "bug", title: "Un titre", body: "Une description." }),
    );
  });
});
