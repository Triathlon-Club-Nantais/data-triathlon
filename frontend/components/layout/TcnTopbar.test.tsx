import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { TcnTopbar } from "./TcnTopbar";

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
}));

vi.mock("@/lib/api/client", () => ({
  apiClient: { listParticipations: vi.fn().mockResolvedValue([]) },
}));

describe("TcnTopbar — visibilité des onglets (issue #10)", () => {
  it("affiche les onglets conservés : Tableau de bord, Résultats, Club", () => {
    render(<TcnTopbar />);
    expect(screen.getByRole("link", { name: "Tableau de bord" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Résultats" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Club" })).toBeInTheDocument();
  });

  it("n'affiche pas les onglets masqués : Carte et Admin", () => {
    render(<TcnTopbar />);
    expect(screen.queryByRole("link", { name: "Carte" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Admin" })).not.toBeInTheDocument();
  });
});
