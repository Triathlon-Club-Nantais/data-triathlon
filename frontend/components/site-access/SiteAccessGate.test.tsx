import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiError } from "@/lib/api/client";

const { siteAccessLogin, push } = vi.hoisted(() => ({
  siteAccessLogin: vi.fn(),
  push: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { siteAccessLogin } };
});

vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

import { SiteAccessGate } from "./SiteAccessGate";

describe("SiteAccessGate", () => {
  beforeEach(() => {
    siteAccessLogin.mockReset();
    push.mockReset();
  });

  it("redirige vers l'accueil après une connexion réussie", async () => {
    siteAccessLogin.mockResolvedValue(null);
    render(<SiteAccessGate />);

    await userEvent.type(screen.getByLabelText(/mot de passe/i), "secret-du-club");
    await userEvent.click(screen.getByRole("button", { name: /se connecter/i }));

    expect(siteAccessLogin).toHaveBeenCalledWith("secret-du-club");
    expect(push).toHaveBeenCalledWith("/");
  });

  it("affiche une erreur sur un mot de passe refusé", async () => {
    siteAccessLogin.mockRejectedValue(new ApiError(401, "Mot de passe incorrect."));
    render(<SiteAccessGate />);

    await userEvent.type(screen.getByLabelText(/mot de passe/i), "mauvais-mot-de-passe");
    await userEvent.click(screen.getByRole("button", { name: /se connecter/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/mot de passe incorrect/i);
    expect(push).not.toHaveBeenCalled();
  });
});
