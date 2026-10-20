import { QueryClient, QueryClientProvider, onlineManager } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
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
  const session = { id: 1, permissions: [], athlete: { id: 9, prenom: "Moi", nom: "Même" } };
  client.setQueryData(queryKeys.session(), connecte ? session : null);
  return render(
    <QueryClientProvider client={client}>
      <MesDeclarations />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  getMyVolunteerDeclarations.mockReset();
});

afterEach(() => {
  onlineManager.setOnline(true);
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

  it("dit « Pour vous » pour sa propre fiche et nomme un statut inconnu", async () => {
    getMyVolunteerDeclarations.mockResolvedValue([declaration({ athlete_id: 9, status: "archivee" })]);
    afficher();

    expect(await screen.findByText(/Pour vous/)).toBeInTheDocument();
    expect(screen.getByText("Statut inconnu")).toBeInTheDocument();
  });

  it("annonce le chargement puis le nombre de déclarations", async () => {
    getMyVolunteerDeclarations.mockResolvedValue([declaration({}), declaration({ id: 2 })]);
    afficher();

    expect(screen.getByRole("status")).toHaveTextContent("Chargement de vos déclarations");
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("2 déclarations."));
  });

  it("garde le squelette, pas l'état vide, tant que la requête est suspendue", () => {
    onlineManager.setOnline(false);
    afficher();

    expect(screen.getByTestId("mes-declarations-squelette")).toBeInTheDocument();
    expect(screen.queryByText(/rien déclaré/)).not.toBeInTheDocument();
  });

  it("dit l'absence de déclaration", async () => {
    getMyVolunteerDeclarations.mockResolvedValue([]);
    afficher();

    expect(await screen.findByText(/Vous n'avez encore rien déclaré/)).toBeInTheDocument();
  });

  it("dit l'échec du chargement et propose de réessayer", async () => {
    getMyVolunteerDeclarations.mockRejectedValue(new Error("réseau"));
    afficher();

    expect(await screen.findByText(/pas pu être chargées/)).toBeInTheDocument();
    getMyVolunteerDeclarations.mockResolvedValue([declaration({})]);
    await userEvent.click(screen.getByRole("button", { name: "Réessayer" }));
    expect(await screen.findByText("Buvette")).toBeInTheDocument();
  });
});
