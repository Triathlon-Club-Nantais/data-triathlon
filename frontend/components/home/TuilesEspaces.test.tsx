import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { SessionUser } from "@/lib/types";

const { getSession, getAdminBadgeCounts } = vi.hoisted(() => ({ getSession: vi.fn(), getAdminBadgeCounts: vi.fn() }));
vi.mock("@/lib/api/client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api/client")>()),
  apiClient: { getSession, getAdminBadgeCounts },
}));
const athlete = vi.hoisted(() => ({ current: null as null | { id: number; prenom: string; nom: string } }));
vi.mock("@/components/layout/AthletePicker", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/components/layout/AthletePicker")>()),
  useSelectedAthlete: () => athlete.current,
}));

import { TuilesEspaces } from "./TuilesEspaces";

const BASE: SessionUser = {
  id: 1, email: "moi@exemple.fr", display_name: "Moi", created_at: "2026-01-01T00:00:00Z",
  permissions: [], roles: [], groups: [], can_administer: false, can_supervise: false,
};

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <TuilesEspaces derniereEpreuve={{ nom: "Tri de Saint-Gilles M", date: "2026-10-11" }} podiumsSaison={27} />
    </QueryClientProvider>,
  );
}

describe("TuilesEspaces", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    athlete.current = null;
    getAdminBadgeCounts.mockResolvedValue({});
  });

  it("links every visitor to Résultats, Club and Mon espace, with their fresh line", async () => {
    getSession.mockResolvedValue(null);
    afficher();
    expect(screen.getByRole("link", { name: /Résultats.*Tri de Saint-Gilles M/ })).toHaveAttribute("href", "/resultats");
    expect(screen.getByRole("link", { name: /Club.*27 podiums/ })).toHaveAttribute("href", "/club");
    expect(screen.getByRole("link", { name: /Mon espace.*Choisissez votre nom/ })).toHaveAttribute("href", "/mon-espace");
  });

  it("names the selected athlete on the Mon espace tile", () => {
    getSession.mockResolvedValue(null);
    athlete.current = { id: 7, prenom: "Léa", nom: "Écuyer" };
    afficher();
    expect(screen.getByRole("link", { name: /Mon espace.*Léa Écuyer/ })).toBeInTheDocument();
  });

  it("shows no reserved tile without power, nor while the session is read", async () => {
    getSession.mockReturnValue(new Promise(() => {}));
    afficher();
    expect(screen.queryByRole("link", { name: /Encadrement|Back-office/ })).not.toBeInTheDocument();
  });

  it("adds Encadrement and Back-office with its « à traiter » badge for those who hold them", async () => {
    getSession.mockResolvedValue({ ...BASE, can_supervise: true, can_administer: true, permissions: ["quality:override"] });
    getAdminBadgeCounts.mockResolvedValue({ quality: 4 });
    afficher();
    expect(await screen.findByRole("link", { name: /Encadrement/ })).toHaveAttribute("href", "/encadrement");
    const backOffice = await screen.findByRole("link", { name: /Back-office/ });
    expect(backOffice).toHaveAttribute("href", "/admin");
    expect(await within(backOffice).findByText("4")).toBeInTheDocument();
    expect(backOffice).toHaveAccessibleName(/4 éléments à traiter/);
  });
});
