import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { queryKeys } from "@/lib/queries/keys";
import type { MyVolunteerDeclarationOut } from "@/lib/types";

const { getMyVolunteerDeclarations } = vi.hoisted(() => ({ getMyVolunteerDeclarations: vi.fn() }));
vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { ...original.apiClient, getMyVolunteerDeclarations } };
});

import { MesDeclarations } from "./MesDeclarations";

const declaration = (extra: Partial<MyVolunteerDeclarationOut>): MyVolunteerDeclarationOut => ({
  id: 1,
  athlete_id: 7,
  athlete_nom: "Martin",
  athlete_prenom: "Léa",
  season: 2026,
  title: "Buvette",
  description: "Stand du club",
  status: "en_attente",
  created_at: "2026-10-12T10:00:00Z",
  ...extra,
});

function afficher(connecte = true) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
  client.setQueryData(queryKeys.session(), connecte ? { id: 1, permissions: [], athlete: null } : null);
  return render(
    <QueryClientProvider client={client}>
      <MesDeclarations />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  getMyVolunteerDeclarations.mockReset();
});

describe("MesDeclarations (#1672)", () => {
  it("ne rend rien pour un visiteur sans session", () => {
    const { container } = afficher(false);

    expect(container).toBeEmptyDOMElement();
    expect(getMyVolunteerDeclarations).not.toHaveBeenCalled();
  });

  it("liste mes déclarations avec l'athlète crédité et leur statut", async () => {
    getMyVolunteerDeclarations.mockResolvedValue([
      declaration({}),
      declaration({ id: 2, title: "Balisage", athlete_prenom: "Paul", athlete_nom: "Durand", status: "validee" }),
      declaration({ id: 3, title: "Chrono", status: "refusee" }),
    ]);
    afficher();

    expect(await screen.findByText("Buvette")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Mes déclarations" })).toBeInTheDocument();
    expect(screen.getByText(/Paul Durand/)).toBeInTheDocument();
    expect(screen.getByText("En attente")).toBeInTheDocument();
    expect(screen.getByText("Validée")).toBeInTheDocument();
    expect(screen.getByText("Refusée")).toBeInTheDocument();
  });

  it("dit l'absence de déclaration", async () => {
    getMyVolunteerDeclarations.mockResolvedValue([]);
    afficher();

    expect(await screen.findByText("Aucune déclaration pour l'instant")).toBeInTheDocument();
  });

  it("dit l'échec du chargement", async () => {
    getMyVolunteerDeclarations.mockRejectedValue(new Error("réseau"));
    afficher();

    expect(await screen.findByText(/pas pu être chargées/)).toBeInTheDocument();
  });
});
