import { describe, it, expect, vi, beforeEach } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const { siteAccessLogout, replace, refresh, toastError } = vi.hoisted(() => ({
  siteAccessLogout: vi.fn(),
  replace: vi.fn(),
  refresh: vi.fn(),
  toastError: vi.fn(),
}));

vi.mock("@/lib/api/client", () => ({ apiClient: { siteAccessLogout: () => siteAccessLogout() } }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace, refresh }) }));
vi.mock("sonner", () => ({ toast: { error: toastError } }));

import { ForgetSiteAccessButton } from "./ForgetSiteAccessButton";

const NOM = "Oublier le code d'accès sur cet appareil";

beforeEach(() => {
  vi.clearAllMocks();
});

// #1057 : sur un poste partagé, le cookie `httponly` ne se retire que par ce geste.
describe("ForgetSiteAccessButton", () => {
  it("efface la session d'accès puis rejoue la page sur place, où la garde la referme", async () => {
    siteAccessLogout.mockResolvedValue(null);
    render(<ForgetSiteAccessButton />);

    await userEvent.click(screen.getByRole("button", { name: NOM }));

    await waitFor(() => expect(refresh).toHaveBeenCalled());
    expect(siteAccessLogout).toHaveBeenCalledTimes(1);
    // Pas de `/acces` : le formulaire se rend sur l'URL courante, destination
    // comprise (règle de #513).
    expect(replace).not.toHaveBeenCalled();
    expect(toastError).not.toHaveBeenCalled();
  });

  it("dit « Oubli en cours… » pendant la requête", async () => {
    let finir!: () => void;
    siteAccessLogout.mockReturnValue(new Promise<null>((resolve) => (finir = () => resolve(null))));
    render(<ForgetSiteAccessButton />);

    await userEvent.click(screen.getByRole("button", { name: NOM }));

    const bouton = screen.getByRole("button", { name: "Oubli en cours…" });
    expect(bouton).toHaveAttribute("aria-busy", "true");
    await act(async () => finir());
    expect(screen.getByRole("button", { name: NOM })).toHaveAttribute("aria-busy", "false");
  });

  it("porte une cible tactile de 44 px sous md", () => {
    render(<ForgetSiteAccessButton />);
    expect(screen.getByRole("button", { name: NOM })).toHaveClass("tcn-cible-tactile");
  });

  // Le pied de page vit dans le layout racine : le bouton n'est pas remonté
  // entre deux usages, il doit donc se réarmer après un succès.
  it("fonctionne encore après un premier oubli suivi d'une nouvelle saisie du code", async () => {
    siteAccessLogout.mockResolvedValue(null);
    render(<ForgetSiteAccessButton />);
    const bouton = screen.getByRole("button", { name: NOM });

    await userEvent.click(bouton);
    await waitFor(() => expect(refresh).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(bouton).toHaveAttribute("aria-busy", "false"));

    await userEvent.click(bouton);
    await waitFor(() => expect(siteAccessLogout).toHaveBeenCalledTimes(2));
    expect(refresh).toHaveBeenCalledTimes(2);
  });

  it("reste sur place et le dit si l'effacement échoue", async () => {
    siteAccessLogout.mockRejectedValue(new Error("réseau"));
    render(<ForgetSiteAccessButton />);

    await userEvent.click(screen.getByRole("button", { name: NOM }));

    await waitFor(() => expect(toastError).toHaveBeenCalled());
    expect(refresh).not.toHaveBeenCalled();
  });
});
