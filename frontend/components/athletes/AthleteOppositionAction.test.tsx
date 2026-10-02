import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { SessionUser } from "@/lib/types";
import { AthleteOppositionAction } from "./AthleteOppositionAction";

const { getSession, previewOpposition, applyOpposition } = vi.hoisted(() => ({
  getSession: vi.fn(),
  previewOpposition: vi.fn(),
  applyOpposition: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { getSession, previewOpposition, applyOpposition } };
});

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

const { replace } = vi.hoisted(() => ({ replace: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace }) }));

const ADMIN: SessionUser = {
  id: 1,
  email: "admin@exemple.fr",
  display_name: "Admin",
  created_at: "2026-01-01T00:00:00Z",
  permissions: ["oppositions:manage"],
  roles: [],
  groups: [],
  can_administer: true,
};

const ATHLETE = { id: 42, nom: "DUPONT", prenom: "Jean", club: null };

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <AthleteOppositionAction athlete={ATHLETE} />
    </QueryClientProvider>,
  );
}

describe("AthleteOppositionAction (#334)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getSession.mockResolvedValue(ADMIN);
    previewOpposition.mockResolvedValue({ athletes: 1, results: 3, already_opposed: false });
    applyOpposition.mockResolvedValue({ id: 7 });
  });

  it("ne s'affiche pas sans le pouvoir oppositions:manage", async () => {
    getSession.mockResolvedValue({ ...ADMIN, permissions: ["athletes:write"] });
    afficher();
    await waitFor(() => expect(getSession).toHaveBeenCalled());
    expect(screen.queryByRole("button", { name: /opposition/i })).not.toBeInTheDocument();
  });

  it("annonce le nombre de résultats, demande la date, puis applique après confirmation", async () => {
    const user = userEvent.setup();
    afficher();

    await user.click(await screen.findByRole("button", { name: "Appliquer une opposition pour Jean DUPONT" }));
    expect(previewOpposition).toHaveBeenCalledWith({ athlete_id: 42 });
    const dialogue = await screen.findByRole("dialog");
    expect(dialogue).toHaveTextContent(/3 résultats/);
    expect(dialogue).toHaveTextContent(/définitif/i);

    const date = screen.getByLabelText(/date de la demande/i);
    await user.clear(date);
    await user.type(date, "2026-09-20");
    await user.click(screen.getByRole("button", { name: /anonymiser définitivement/i }));

    await waitFor(() =>
      expect(applyOpposition).toHaveBeenCalledWith({ athlete_id: 42, requested_on: "2026-09-20" }),
    );
    expect(replace).toHaveBeenCalledWith("/resultats");
  });

  it("dit que le décompte a échoué, pas l'opposition, et comment réessayer", async () => {
    previewOpposition.mockRejectedValue(new Error("réseau"));
    const user = userEvent.setup();
    afficher();

    await user.click(await screen.findByRole("button", { name: "Appliquer une opposition pour Jean DUPONT" }));

    const alerte = await screen.findByRole("alert");
    expect(alerte).toHaveTextContent(/décompte impossible/i);
    expect(alerte).toHaveTextContent(/rouvrez/i);
    expect(screen.getByRole("button", { name: /anonymiser définitivement/i })).toBeDisabled();
  });

  it("prévient quand des homonymes seront aussi anonymisés", async () => {
    previewOpposition.mockResolvedValue({ athletes: 2, results: 5, already_opposed: false });
    const user = userEvent.setup();
    afficher();

    await user.click(await screen.findByRole("button", { name: "Appliquer une opposition pour Jean DUPONT" }));

    expect(await screen.findByRole("dialog")).toHaveTextContent(/2 fiches.*même nom/i);
  });
});
