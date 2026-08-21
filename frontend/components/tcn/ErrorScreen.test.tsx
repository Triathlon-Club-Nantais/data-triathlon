import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";

import { ErrorScreen } from "./ErrorScreen";

describe("ErrorScreen", () => {
  it("annonce l'échec par un titre de page et une région d'alerte (#464, ETAT-1)", () => {
    render(<ErrorScreen onRetry={vi.fn()} />);

    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      /n'a pas pu s'afficher/i,
    );
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("dit quoi faire, pas seulement que ça a échoué", () => {
    render(<ErrorScreen onRetry={vi.fn()} />);

    expect(screen.getByText(/nouvel essai suffit/i)).toBeInTheDocument();
  });

  it("« Réessayer » déclenche la nouvelle tentative", async () => {
    const reessayer = vi.fn();
    const user = userEvent.setup();
    render(<ErrorScreen onRetry={reessayer} />);

    await user.click(screen.getByRole("button", { name: "Réessayer" }));

    expect(reessayer).toHaveBeenCalledTimes(1);
  });

  it("offre une sortie en plus de la nouvelle tentative, qui refait la même chose", () => {
    render(<ErrorScreen onRetry={vi.fn()} />);

    expect(screen.getByRole("link", { name: /tableau de bord/i })).toHaveAttribute(
      "href",
      "/dashboard",
    );
  });

  it("affiche le code d'incident pour qu'un signalement soit exploitable", () => {
    render(<ErrorScreen onRetry={vi.fn()} digest="4f3c9a12" />);

    expect(screen.getByText(/4f3c9a12/)).toBeInTheDocument();
  });

  it("ne parle pas de code d'incident quand Next.js n'en fournit aucun", () => {
    render(<ErrorScreen onRetry={vi.fn()} />);

    expect(screen.queryByText(/code de l'incident/i)).not.toBeInTheDocument();
  });
});
