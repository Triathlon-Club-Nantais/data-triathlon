import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { AthleteAlias, SessionUser } from "@/lib/types";
import { AthleteVariantsPanel } from "./AthleteVariantsPanel";

const { getSession, listAthleteAliases, removeAthleteAlias } = vi.hoisted(() => ({
  getSession: vi.fn(),
  listAthleteAliases: vi.fn(),
  removeAthleteAlias: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: { ...original.apiClient, getSession, listAthleteAliases, removeAthleteAlias },
  };
});

function session(permissions: string[]): SessionUser {
  return { id: 7, email: "admin@exemple.fr", permissions, roles: [] } as unknown as SessionUser;
}

const VARIANTE: AthleteAlias = {
  id: 4644,
  last_name_key: "jacques",
  first_name_key: "daniel",
  created_at: "2026-10-05T10:00:00Z",
};

function afficher() {
  document.cookie = "tcn_logged_in=1; path=/";
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <AthleteVariantsPanel athleteId={49610} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("AthleteVariantsPanel", () => {
  it("ne rend rien et ne lit rien sans athletes:write", async () => {
    getSession.mockResolvedValue(session(["athletes:read"]));

    const { container } = afficher();

    await waitFor(() => expect(getSession).toHaveBeenCalled());
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(container).toBeEmptyDOMElement();
    expect(listAthleteAliases).not.toHaveBeenCalled();
  });

  it("ne rend rien pour une fiche sans variante", async () => {
    getSession.mockResolvedValue(session(["athletes:write"]));
    listAthleteAliases.mockResolvedValue({ aliases: [] });

    const { container } = afficher();

    await waitFor(() => expect(listAthleteAliases).toHaveBeenCalledWith(49610));
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(container).toBeEmptyDOMElement();
  });

  it("liste les variantes sous l'ancre #variantes", async () => {
    getSession.mockResolvedValue(session(["athletes:write"]));
    listAthleteAliases.mockResolvedValue({ aliases: [VARIANTE] });

    const { container } = afficher();

    expect(await screen.findByText("JACQUES daniel")).toBeInTheDocument();
    expect(container.querySelector("#variantes")).not.toBeNull();
  });

  it("retirer demande confirmation puis supprime la variante", async () => {
    getSession.mockResolvedValue(session(["athletes:write"]));
    listAthleteAliases.mockResolvedValueOnce({ aliases: [VARIANTE] }).mockResolvedValue({ aliases: [] });
    removeAthleteAlias.mockResolvedValue(undefined);

    afficher();
    await userEvent.click(await screen.findByRole("button", { name: /retirer la variante JACQUES daniel/i }));
    expect(removeAthleteAlias).not.toHaveBeenCalled();
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Retirer" }));

    await waitFor(() => expect(removeAthleteAlias).toHaveBeenCalledWith(49610, 4644));
    await waitFor(() => expect(screen.queryByText("JACQUES daniel")).not.toBeInTheDocument());
  });
});
