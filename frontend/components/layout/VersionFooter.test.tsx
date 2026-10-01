import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";

// process.env est figé à l'import de VersionFooter (Next.js le remplace au
// build). On stubbe donc l'env AVANT `import()` du module — sinon la constante
// `FRONT_VERSION` capture "dev" et les assertions sur `v0.1.3` échouent.
vi.stubEnv("NEXT_PUBLIC_APP_VERSION", "v0.1.3");

const getVersion = vi.fn();

vi.mock("@/lib/api/client", () => ({
  apiClient: {
    getVersion: () => getVersion(),
  },
}));

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn(), refresh: vi.fn() }) }));

import { VersionFooter } from "./VersionFooter";
import { SiteAccessOpenMarker } from "@/components/site-access/site-access-open";

beforeEach(() => {
  getVersion.mockReset();
});

describe("VersionFooter (#134)", () => {
  it("affiche silencieusement la version quand front et back sont alignés", async () => {
    getVersion.mockResolvedValue({ version: "v0.1.3" });
    render(<VersionFooter />);
    // Rendu initial synchrone : version front visible dès le premier frame,
    // pas de spinner clignotant.
    expect(screen.getByText("v0.1.3")).toBeInTheDocument();
    // Puis le fetch résout ; l'affichage reste calme.
    await waitFor(() => expect(getVersion).toHaveBeenCalledTimes(1));
    expect(screen.getByText("v0.1.3")).toBeInTheDocument();
    // Aucun préfixe « front » / « back » n'apparaît quand ça matche.
    expect(screen.queryByText(/front/)).not.toBeInTheDocument();
    expect(screen.queryByText(/back/)).not.toBeInTheDocument();
  });

  it("signale explicitement le mismatch front/back", async () => {
    getVersion.mockResolvedValue({ version: "v0.1.2" });
    render(<VersionFooter />);
    await waitFor(() =>
      expect(screen.getByText(/front/)).toBeInTheDocument(),
    );
    // Les deux versions sont visibles, préfixées, pour qu'un utilisateur qui
    // remonte un bug puisse les recopier.
    expect(screen.getByText("v0.1.3")).toBeInTheDocument();
    expect(screen.getByText("v0.1.2")).toBeInTheDocument();
    expect(screen.getByText(/back/)).toBeInTheDocument();
  });

  it("dégrade proprement quand le back est injoignable", async () => {
    getVersion.mockRejectedValue(new Error("network"));
    render(<VersionFooter />);
    // L'utilisateur voit AU MOINS sa version front + un signal que le back
    // n'a pas répondu — mieux que rien pour un bug report.
    await waitFor(() =>
      expect(screen.getByText(/back \?/)).toBeInTheDocument(),
    );
    expect(screen.getByText("v0.1.3")).toBeInTheDocument();
  });

  // #1057 : visible de tous, connectés ou non, quel que soit l'état des
  // versions, mais seulement là où le code a été accepté (le marqueur est posé
  // par `app/(public_restricted)/layout.tsx`).
  it.each([
    ["alignées", () => getVersion.mockResolvedValue({ version: "v0.1.3" })],
    ["divergentes", () => getVersion.mockResolvedValue({ version: "v0.1.2" })],
    ["back injoignable", () => getVersion.mockRejectedValue(new Error("network"))],
  ])("porte le geste « Oublier le code d'accès » (versions %s)", async (_cas, preparer) => {
    preparer();
    render(
      <>
        <SiteAccessOpenMarker />
        <VersionFooter />
      </>,
    );
    await waitFor(() => expect(getVersion).toHaveBeenCalled());
    const pied = screen.getByRole("contentinfo");
    expect(
      await within(pied).findByRole("button", { name: "Oublier le code d'accès sur cet appareil" }),
    ).toBeInTheDocument();
  });

  it("tait le geste là où le code n'a pas été accepté (/acces, formulaire du code)", async () => {
    getVersion.mockResolvedValue({ version: "v0.1.3" });
    render(<VersionFooter />);
    await waitFor(() => expect(getVersion).toHaveBeenCalled());
    expect(
      screen.queryByRole("button", { name: "Oublier le code d'accès sur cet appareil" }),
    ).not.toBeInTheDocument();
  });

  it("porte les liens légaux, même sans code d'accès saisi (#333)", async () => {
    getVersion.mockResolvedValue({ version: "v0.1.3" });
    render(<VersionFooter />);
    await waitFor(() => expect(getVersion).toHaveBeenCalled());
    const pied = screen.getByRole("contentinfo");
    const liens = within(pied).getByRole("navigation", { name: "Informations légales" });
    expect(within(liens).getByRole("link", { name: "Confidentialité" })).toHaveAttribute("href", "/confidentialite");
  });
});
