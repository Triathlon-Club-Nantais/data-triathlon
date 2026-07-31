import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

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

import { VersionFooter } from "./VersionFooter";

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
});
