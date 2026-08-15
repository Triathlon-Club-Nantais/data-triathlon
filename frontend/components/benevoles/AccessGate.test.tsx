import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { ApiError } from "@/lib/api/client";

const { benevoleLogin } = vi.hoisted(() => ({ benevoleLogin: vi.fn() }));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { benevoleLogin } };
});

import { AccessGate } from "./AccessGate";

describe("AccessGate", () => {
  it("affiche un formulaire de mot de passe", () => {
    render(<AccessGate onSuccess={vi.fn()} />);
    expect(screen.getByLabelText(/mot de passe/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /se connecter/i })).toBeInTheDocument();
  });

  it("appelle onSuccess après une connexion réussie", async () => {
    benevoleLogin.mockResolvedValue(null);
    const onSuccess = vi.fn();
    const user = userEvent.setup();
    render(<AccessGate onSuccess={onSuccess} />);

    await user.type(screen.getByLabelText(/mot de passe/i), "secret-du-club");
    await user.click(screen.getByRole("button", { name: /se connecter/i }));

    await waitFor(() => expect(onSuccess).toHaveBeenCalled());
    expect(benevoleLogin).toHaveBeenCalledWith("secret-du-club");
  });

  it("affiche un message d'erreur français sur mot de passe incorrect", async () => {
    benevoleLogin.mockRejectedValue(new ApiError(401, "Mot de passe incorrect."));
    const user = userEvent.setup();
    render(<AccessGate onSuccess={vi.fn()} />);

    await user.type(screen.getByLabelText(/mot de passe/i), "faux");
    await user.click(screen.getByRole("button", { name: /se connecter/i }));

    expect(await screen.findByText("Mot de passe incorrect.")).toBeInTheDocument();
  });

  it("ne rend pas le bouton actionnable pendant la requête", async () => {
    let resoudre: (() => void) | undefined;
    benevoleLogin.mockReturnValue(
      new Promise<null>((resolve) => {
        resoudre = () => resolve(null);
      }),
    );
    const user = userEvent.setup();
    render(<AccessGate onSuccess={vi.fn()} />);
    const bouton = screen.getByRole("button", { name: /se connecter/i });

    await user.type(screen.getByLabelText(/mot de passe/i), "secret-du-club");
    await user.click(bouton);

    expect(bouton).toBeDisabled();
    resoudre?.();
  });
});
