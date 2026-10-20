import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ResultClaim, TeamResult } from "@/lib/types";

const { searchMyTeamResults, getMyResultClaims, requestResultClaim } = vi.hoisted(() => ({
  searchMyTeamResults: vi.fn(),
  getMyResultClaims: vi.fn(),
  requestResultClaim: vi.fn(),
}));
vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { ...original.apiClient, searchMyTeamResults, getMyResultClaims, requestResultClaim } };
});

import { ResultatEquipeManquant } from "./ResultatEquipeManquant";

const EQUIPE: TeamResult = {
  participation_id: 5, team_name: "Les Mollets d'Acier", course_id: 9, course_name: "Swimrun de Nantes",
  event_date: "2026-05-10", rank_overall: 3, total_time: "3:12:45", teammates: ["Paul Durand", "Ana Roy"],
};
const demande = (status: ResultClaim["status"], kind: ResultClaim["kind"] = "team"): ResultClaim =>
  ({ id: 1, participation_id: 5, kind, status, created_at: "2026-10-01T10:00:00Z" });

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ResultatEquipeManquant />
    </QueryClientProvider>,
  );
}

async function chercher(saisie: string) {
  await userEvent.type(screen.getByLabelText("Nom de l'équipe"), saisie);
  await userEvent.click(screen.getByRole("button", { name: "Chercher" }));
}

beforeEach(() => {
  vi.clearAllMocks();
  searchMyTeamResults.mockResolvedValue([EQUIPE]);
  getMyResultClaims.mockResolvedValue([]);
  requestResultClaim.mockResolvedValue(demande("pending"));
});

describe("ResultatEquipeManquant (#1739)", () => {
  it("cherche_par_nom_et_affiche_les_lignes", async () => {
    afficher();
    expect(screen.getByText("Un résultat d'équipe manque ?")).toBeInTheDocument();
    await chercher("mollets");
    expect(await screen.findByText("Les Mollets d'Acier")).toBeInTheDocument();
    expect(searchMyTeamResults).toHaveBeenCalledWith("mollets");
    expect(screen.getByText(/Swimrun de Nantes/)).toBeInTheDocument();
    expect(screen.getByText(/3:12:45/)).toBeInTheDocument();
    expect(screen.getByText(/Paul Durand, Ana Roy/)).toBeInTheDocument();
  });

  it("bouton_chercher_inerte_sous_trois_caracteres", async () => {
    afficher();
    await chercher("mo");
    expect(screen.getByRole("button", { name: "Chercher" })).toHaveAttribute("aria-disabled", "true");
    expect(searchMyTeamResults).not.toHaveBeenCalled();
  });

  it("etat_vide_cite_la_saisie", async () => {
    searchMyTeamResults.mockResolvedValue([]);
    afficher();
    await chercher("zzz");
    expect(await screen.findByText("Aucun résultat d'équipe ne correspond à « zzz ».")).toBeInTheDocument();
  });

  it("un_clic_envoie_une_demande_d_equipe", async () => {
    afficher();
    await chercher("mollets");
    const bouton = await screen.findByRole("button", { name: "C'était mon équipe : Les Mollets d'Acier, Swimrun de Nantes" });
    getMyResultClaims.mockResolvedValue([demande("pending")]);
    await userEvent.click(bouton);
    expect(requestResultClaim).toHaveBeenCalledWith(5, "team");
    expect(await screen.findByText("Demande envoyée, le club va vérifier.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /C'était mon équipe/ })).not.toBeInTheDocument();
  });

  it("une_demande_refusee_peut_etre_renvoyee", async () => {
    getMyResultClaims.mockResolvedValue([demande("rejected")]);
    afficher();
    await chercher("mollets");
    expect(await screen.findByText("Demande refusée par le club.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /C'était mon équipe/ }));
    expect(requestResultClaim).toHaveBeenCalledWith(5, "team");
  });

  it("le_refus_du_serveur_s_affiche", async () => {
    requestResultClaim.mockRejectedValue(new Error("Vous avez déjà un résultat sur cette épreuve."));
    afficher();
    await chercher("mollets");
    await userEvent.click(await screen.findByRole("button", { name: /C'était mon équipe/ }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Vous avez déjà un résultat sur cette épreuve."));
  });
});
