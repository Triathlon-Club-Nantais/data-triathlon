import { beforeEach, describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const { getSession } = vi.hoisted(() => ({ getSession: vi.fn() }));
vi.mock("@/lib/api/server", () => ({ apiServer: { getSession } }));

import GuidePage from "./page";

const session = (permissions: string[]) => ({
  id: 1,
  email: "membre@exemple.fr",
  display_name: "Membre",
  created_at: "2026-09-01T00:00:00Z",
  permissions,
  roles: [],
  groups: [],
  can_administer: false,
});

beforeEach(() => {
  vi.clearAllMocks();
  getSession.mockResolvedValue(null);
});

describe("GuidePage", () => {
  it("rend le sommaire et les 6 sections ouvertes à tous", async () => {
    render(await GuidePage());
    expect(screen.getByRole("heading", { name: /guide/i, level: 1 })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Sommaire du guide" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Tableau de bord" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Espace club" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Résultats" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Fiche athlète" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Comparaison" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Ajouter une épreuve" })).toBeInTheDocument();
  });

  // #879 : le guide ne mène pas à un écran que le rail tait à ce visiteur.
  it("tait la section « Bénévolat » sans pages:preview, sommaire compris", async () => {
    getSession.mockResolvedValue(session([]));
    render(await GuidePage());
    expect(screen.queryByRole("heading", { name: "Bénévolat" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Bénévolat" })).not.toBeInTheDocument();
  });

  it("montre la section « Bénévolat » à qui porte pages:preview", async () => {
    getSession.mockResolvedValue(session(["pages:preview"]));
    render(await GuidePage());
    expect(screen.getByRole("heading", { name: "Bénévolat" })).toBeInTheDocument();
  });

  it("expose la section « club » sous une ancre atteignable directement", async () => {
    const { container } = render(await GuidePage());
    expect(container.querySelector("#club")).not.toBeNull();
  });
});
