import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { AthleteLink } from "@/lib/types";

const { getAthleteLinks, detachAthleteLink } = vi.hoisted(() => ({
  getAthleteLinks: vi.fn(),
  detachAthleteLink: vi.fn(),
}));
vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { getAthleteLinks, detachAthleteLink } };
});
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

import { AthleteLinksTable } from "./AthleteLinksTable";

const ANCIEN: AthleteLink = {
  user: { id: 12, display_name: "Paul D.", email: "paul@exemple.fr" },
  athlete: { id: 7, prenom: "Paul", nom: "Durand", club: null },
  licensed_this_season: false,
};
const LEA: AthleteLink = {
  user: { id: 13, display_name: "", email: "lea@exemple.fr" },
  athlete: { id: 42, prenom: "Léa", nom: "Martin", club: "TCN" },
  licensed_this_season: true,
};

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <AthleteLinksTable />
    </QueryClientProvider>,
  );
}

beforeEach(() => vi.clearAllMocks());

describe("AthleteLinksTable (#1633)", () => {
  it("says, for each linked account, whether the link still makes a member this season", async () => {
    getAthleteLinks.mockResolvedValue([ANCIEN, LEA]);
    afficher();

    const ancien = (await screen.findByText("paul@exemple.fr")).closest("tr") as HTMLElement;
    expect(ancien).toHaveTextContent("Pas de licence cette saison");
    expect(within(ancien).getByRole("link", { name: "Paul Durand" })).toHaveAttribute("href", "/athletes/7");
    const lea = screen.getByText("lea@exemple.fr").closest("tr") as HTMLElement;
    expect(lea).toHaveTextContent("Licencié cette saison");
  });

  it("detaches an account after confirmation", async () => {
    getAthleteLinks.mockResolvedValue([ANCIEN]);
    detachAthleteLink.mockResolvedValue(null);
    afficher();

    await userEvent.click(await screen.findByRole("button", { name: "Détacher Paul D. de sa fiche" }));
    expect(detachAthleteLink).not.toHaveBeenCalled();
    await userEvent.click(await screen.findByRole("button", { name: "Détacher" }));

    await waitFor(() => expect(detachAthleteLink).toHaveBeenCalledWith(12));
  });

  it("says when no account is linked", async () => {
    getAthleteLinks.mockResolvedValue([]);
    afficher();

    expect(await screen.findByText(/aucun compte rattaché/i)).toBeInTheDocument();
  });
});
