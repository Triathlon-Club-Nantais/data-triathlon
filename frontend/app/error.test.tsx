import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";

const { captureEvent } = vi.hoisted(() => ({ captureEvent: vi.fn() }));
vi.mock("@/lib/posthog", () => ({ captureEvent }));

import ErrorBoundary from "./error";

describe("app/error", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("ne rend jamais le message d'erreur brut (COPY-3 (4), #464)", () => {
    const erreur = Object.assign(new Error("connect ECONNREFUSED 10.0.0.4:5432"), {
      digest: "4f3c9a12",
    });

    render(<ErrorBoundary error={erreur} retry={vi.fn()} />);

    expect(screen.queryByText(/ECONNREFUSED/)).not.toBeInTheDocument();
  });

  it("expose le code d'incident, lui, pour qu'un signalement soit exploitable", () => {
    const erreur = Object.assign(new Error("boum"), { digest: "4f3c9a12" });

    render(<ErrorBoundary error={erreur} retry={vi.fn()} />);

    expect(screen.getByText(/4f3c9a12/)).toBeInTheDocument();
  });

  it("câble « Réessayer » sur retry(), qui refait le fetch, et non sur reset()", async () => {
    const retry = vi.fn();
    const user = userEvent.setup();

    render(<ErrorBoundary error={new Error("boum")} retry={retry} />);
    await user.click(screen.getByRole("button", { name: "Réessayer" }));

    expect(retry).toHaveBeenCalledTimes(1);
  });

  it("signale l'affichage de l'écran de panne à PostHog, avec le digest", () => {
    const erreur = Object.assign(new Error("boum"), { digest: "4f3c9a12" });

    render(<ErrorBoundary error={erreur} retry={vi.fn()} />);

    expect(captureEvent).toHaveBeenCalledWith("error_screen_shown", { digest: "4f3c9a12" });
  });
});
