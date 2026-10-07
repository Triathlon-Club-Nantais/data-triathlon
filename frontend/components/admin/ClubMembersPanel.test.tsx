import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ClubMember, ClubMembersSeason } from "@/lib/types";

const { mutate, unlink } = vi.hoisted(() => ({ mutate: vi.fn(), unlink: vi.fn() }));
vi.mock("@/lib/queries/admin", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/queries/admin")>();
  return {
    ...original,
    useImportClubMembers: () => ({ mutate, isPending: false }),
    useSyncClubMembers: () => ({ mutate: vi.fn(), isPending: false }),
    useLinkClubMember: () => ({ mutate: vi.fn(), isPending: false }),
    useUnlinkClubMember: () => ({ mutate: unlink, isPending: false }),
  };
});

import { ClubMembersImport, ClubMembersPanel } from "./ClubMembersPanel";

function membre(extra: Partial<ClubMember>): ClubMember {
  return {
    id: 1, season: 2026, licence_id: "C1", nom: "MARTIN", prenom: "Anne", gender: "F",
    athlete_id: 5, link_status: "auto", source: "fftri", ...extra,
  };
}

function saison(extra: Partial<ClubMembersSeason>): ClubMembersSeason {
  return { season: 2026, seasons: [2026], total: 0, linked: 0, unlinked: 0, ambiguous: 0, members: [], ...extra };
}

describe("ClubMembersImport", () => {
  it("importe le fichier pour la saison choisie", () => {
    render(<ClubMembersImport defaultSeason={2025} />);
    const fichier = new File(["Nom,Prenom\nA,B\n"], "licencies.csv", { type: "text/csv" });

    fireEvent.change(screen.getByLabelText(/fichier des licenciés/i), { target: { files: [fichier] } });
    fireEvent.click(screen.getByRole("button", { name: /importer/i }));

    expect(mutate).toHaveBeenCalledWith({ season: 2025, file: fichier }, expect.anything());
  });

  it("refuse une saison vide", () => {
    render(<ClubMembersImport defaultSeason={2025} />);
    const fichier = new File(["x"], "licencies.csv", { type: "text/csv" });
    fireEvent.change(screen.getByLabelText(/fichier des licenciés/i), { target: { files: [fichier] } });
    fireEvent.change(screen.getByLabelText(/saison \(année de début\)/i), { target: { value: "" } });

    expect(screen.getByRole("button", { name: /importer/i })).toBeDisabled();
  });
});

describe("ClubMembersPanel", () => {
  const props = { season: 2026, onSeasonChange: vi.fn(), isLoading: false };

  it("recale la saison par défaut de l'import quand la saison affichée change", () => {
    const { rerender } = render(<ClubMembersPanel {...props} data={saison({})} />);
    expect(screen.getByLabelText(/saison \(année de début\)/i)).toHaveValue(2025);

    rerender(<ClubMembersPanel {...props} season={2024} data={saison({ season: 2024 })} />);

    expect(screen.getByLabelText(/saison \(année de début\)/i)).toHaveValue(2023);
  });

  it("invite à relire la liste ou à importer quand la saison est vide", () => {
    render(<ClubMembersPanel {...props} data={saison({})} />);

    expect(screen.getByText(/aucun licencié pour cette saison/i)).toBeInTheDocument();
  });

  it("dit que tout le monde est rattaché quand il ne reste rien à rattacher", () => {
    render(
      <ClubMembersPanel {...props} data={saison({ total: 1, linked: 1, members: [membre({})] })} />,
    );

    expect(screen.getByText(/tous les licenciés sont rattachés/i)).toBeInTheDocument();
    expect(screen.queryByText(/aucun licencié pour cette saison/i)).not.toBeInTheDocument();
  });

  it("accorde « licencié » au singulier", () => {
    render(
      <ClubMembersPanel {...props} data={saison({ total: 1, linked: 1, members: [membre({})] })} />,
    );

    expect(screen.getByText(/^1 licencié :/)).toBeInTheDocument();
  });

  it("nomme le licencié sur le bouton de rattachement", () => {
    render(
      <ClubMembersPanel
        {...props}
        data={saison({
          total: 1, unlinked: 1,
          members: [membre({ nom: "DURAND", prenom: "Paul", athlete_id: null, link_status: "unlinked" })],
        })}
      />,
    );

    expect(screen.getByRole("button", { name: /rattacher durand paul à une fiche/i })).toBeInTheDocument();
  });

  it("liste, repliés, les rattachements faits à la main, et annule l'un", () => {
    render(
      <ClubMembersPanel
        {...props}
        data={saison({
          total: 2, linked: 2,
          members: [membre({}), membre({ id: 2, nom: "DURAND", prenom: "Paul", link_status: "manual" })],
        })}
      />,
    );

    const summary = screen.getByText("Rattachements faits à la main (1)");
    expect(summary.closest("details")).not.toHaveAttribute("open");
    fireEvent.click(screen.getByRole("button", { name: /annuler le rattachement de durand paul/i }));

    expect(unlink).toHaveBeenCalledWith(2, expect.anything());
  });

  it("mène d'un rattachement fait à la main à la fiche rattachée", () => {
    render(
      <ClubMembersPanel
        {...props}
        data={saison({
          total: 1, linked: 1,
          members: [membre({ nom: "DURAND", prenom: "Paul", athlete_id: 4812, link_status: "manual" })],
        })}
      />,
    );

    expect(screen.getByRole("link", { name: "fiche n° 4812" })).toHaveAttribute("href", "/athletes/4812");
  });
});
