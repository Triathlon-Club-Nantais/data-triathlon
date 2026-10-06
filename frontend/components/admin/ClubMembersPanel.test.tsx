import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const { mutate } = vi.hoisted(() => ({ mutate: vi.fn() }));
vi.mock("@/lib/queries/admin", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/queries/admin")>();
  return {
    ...original,
    useImportClubMembers: () => ({ mutate, isPending: false }),
    useSyncClubMembers: () => ({ mutate: vi.fn(), isPending: false }),
    useLinkClubMember: () => ({ mutate: vi.fn(), isPending: false }),
  };
});

import { ClubMembersImport } from "./ClubMembersPanel";

describe("ClubMembersImport", () => {
  it("importe le fichier pour la saison choisie", () => {
    render(<ClubMembersImport defaultSeason={2025} />);
    const fichier = new File(["Nom,Prenom\nA,B\n"], "licencies.csv", { type: "text/csv" });

    fireEvent.change(screen.getByLabelText(/fichier des licenciés/i), { target: { files: [fichier] } });
    fireEvent.click(screen.getByRole("button", { name: /importer/i }));

    expect(mutate).toHaveBeenCalledWith({ season: 2025, file: fichier }, expect.anything());
  });
});
