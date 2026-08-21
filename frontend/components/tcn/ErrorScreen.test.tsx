import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";

const { captureEvent } = vi.hoisted(() => ({ captureEvent: vi.fn() }));
vi.mock("@/lib/posthog", () => ({ captureEvent }));

import { ErrorScreen } from "./ErrorScreen";

describe("ErrorScreen", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

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

  it("offre une sortie ailleurs que sur la page en panne (#464, D1)", () => {
    render(<ErrorScreen onRetry={vi.fn()} />);

    const sortie = screen.getByRole("link", { name: /résultats/i });
    expect(sortie).toHaveAttribute("href", "/resultats");
    // `/dashboard` est la page d'accueil (`app/page.tsx` y redirige) et la plus
    // sujette à la panne : y renvoyer par `next/link` ne change pas le chemin,
    // donc la frontière garderait son état d'erreur et le clic ne ferait rien.
    expect(sortie).not.toHaveAttribute("href", "/dashboard");
  });

  it("affiche le code d'incident pour qu'un signalement soit exploitable", () => {
    render(<ErrorScreen onRetry={vi.fn()} digest="4f3c9a12" />);

    expect(screen.getByText(/4f3c9a12/)).toBeInTheDocument();
  });

  it("ne parle pas de code d'incident quand Next.js n'en fournit aucun", () => {
    render(<ErrorScreen onRetry={vi.fn()} />);

    expect(screen.queryByText(/code de l'incident/i)).not.toBeInTheDocument();
  });

  it("ne renvoie pas à un code absent : sans digest, il oriente vers le bouton", () => {
    render(<ErrorScreen onRetry={vi.fn()} />);

    expect(screen.queryByText(/code ci-dessous/i)).not.toBeInTheDocument();
    expect(screen.getByText(/bulle de signalement/i)).toBeInTheDocument();
  });

  it("renvoie au code quand il existe", () => {
    render(<ErrorScreen onRetry={vi.fn()} digest="4f3c9a12" />);

    expect(screen.getByText(/code ci-dessous/i)).toBeInTheDocument();
  });

  it("signale l'affichage à PostHog, depuis les deux frontières donc depuis ici", () => {
    render(<ErrorScreen onRetry={vi.fn()} digest="4f3c9a12" />);

    expect(captureEvent).toHaveBeenCalledWith("error_screen_shown", { digest: "4f3c9a12" });
  });

  it("signale aussi l'affichage sans digest, en le disant nul plutôt qu'absent", () => {
    render(<ErrorScreen onRetry={vi.fn()} />);

    expect(captureEvent).toHaveBeenCalledWith("error_screen_shown", { digest: null });
  });
});
