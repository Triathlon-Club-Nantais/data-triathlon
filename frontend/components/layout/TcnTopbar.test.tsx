import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
}));

vi.mock("@/lib/api/client", () => ({
  apiClient: { listParticipations: vi.fn().mockResolvedValue([]) },
}));

import { TcnTopbar } from "./TcnTopbar";

describe("TcnTopbar — visibilité des onglets (issues #10, #28)", () => {
  it("affiche les onglets conservés : Tableau de bord et Résultats", () => {
    render(<TcnTopbar />);
    expect(screen.getByRole("link", { name: "Tableau de bord" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Résultats" })).toBeInTheDocument();
  });

  it("n'affiche pas les onglets masqués : Club, Carte et Admin", () => {
    render(<TcnTopbar />);
    expect(screen.queryByRole("link", { name: "Club" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Carte" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Admin" })).not.toBeInTheDocument();
  });
});
