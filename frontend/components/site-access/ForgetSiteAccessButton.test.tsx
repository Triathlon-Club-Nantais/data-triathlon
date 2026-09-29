import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
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

beforeEach(() => {
  vi.clearAllMocks();
});

// #1057 : sur un poste partagé, le cookie `httponly` ne se retire que par ce geste.
describe("ForgetSiteAccessButton", () => {
  it("efface la session d'accès puis mène à /acces", async () => {
    siteAccessLogout.mockResolvedValue(null);
    render(<ForgetSiteAccessButton />);

    await userEvent.click(screen.getByRole("button", { name: "Oublier le code d'accès sur cet appareil" }));

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/acces"));
    expect(siteAccessLogout).toHaveBeenCalledTimes(1);
    expect(refresh).toHaveBeenCalled();
    expect(toastError).not.toHaveBeenCalled();
  });

  it("reste sur place et le dit si l'effacement échoue", async () => {
    siteAccessLogout.mockRejectedValue(new Error("réseau"));
    render(<ForgetSiteAccessButton />);

    await userEvent.click(screen.getByRole("button", { name: "Oublier le code d'accès sur cet appareil" }));

    await waitFor(() => expect(toastError).toHaveBeenCalled());
    expect(replace).not.toHaveBeenCalled();
  });
});
