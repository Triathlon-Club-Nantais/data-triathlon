import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Participation, PublicPageSettings } from "@/lib/types";

const { getPublicPageSettings, savePublicPageSettings, getAthlete } = vi.hoisted(() => ({
  getPublicPageSettings: vi.fn(), savePublicPageSettings: vi.fn(), getAthlete: vi.fn(),
}));
vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { ...original.apiClient, getPublicPageSettings, savePublicPageSettings, getAthlete } };
});

import { ApiError } from "@/lib/api/client";
import { MaFichePublique } from "./MaFichePublique";

const REGLAGES: PublicPageSettings = {
  hide_best_times: false, hide_progression: false, hide_comparison: false,
  links: [], pinned_participation_id: null, shared: false,
};
const resultat = (id: number, name: string, extra = {}) =>
  ({ id, course: { id, name, event_date: "2026-05-17" }, is_pending_validation: false, ...extra }) as unknown as Participation;

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MaFichePublique athleteId={42} /></QueryClientProvider>);
}

beforeEach(() => {
  vi.clearAllMocks();
  getPublicPageSettings.mockResolvedValue(REGLAGES);
  getAthlete.mockResolvedValue({ participations: [resultat(5, "Tri de Nantes"), resultat(6, "En attente", { is_pending_validation: true })] });
});

describe("MaFichePublique (#1692)", () => {
  it("offers the three hide switches, three url fields, the pin and the privacy limit", async () => {
    afficher();

    for (const nom of ["Masquer mes records", "Masquer ma progression", "Masquer la comparaison"]) {
      expect(await screen.findByLabelText(nom)).not.toBeChecked();
    }
    expect(document.querySelectorAll('input[type="url"]')).toHaveLength(3);
    const choix = await screen.findByLabelText("Résultat épinglé");
    expect(await screen.findByRole("option", { name: /Tri de Nantes/ })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: /En attente/ })).toBeNull();
    expect(choix).toHaveValue("");
    expect(screen.getByRole("option", { name: "Aucun" })).toBeInTheDocument();
    expect(screen.getByText(/Masquer un bloc n'efface rien : vos résultats restent publics et permettent de le recalculer\./)).toBeInTheDocument();
    expect(screen.getByText(/Votre fiche reste trouvable comme adversaire dans la comparaison d'une autre fiche\./)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Voir ma fiche" })).toHaveAttribute("href", "/athletes/42");
  });

  it("saves the body and announces it in a region mounted from the start", async () => {
    savePublicPageSettings.mockResolvedValue({ ...REGLAGES, hide_progression: true });
    afficher();

    await userEvent.click(await screen.findByLabelText("Masquer ma progression"));
    await userEvent.type(screen.getAllByLabelText(/Lien/)[0], "https://strava.com/athletes/1");
    await userEvent.selectOptions(await screen.findByLabelText("Résultat épinglé"), "5");
    const annonce = screen.getByRole("status");
    expect(annonce).toHaveTextContent("");
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));

    await waitFor(() =>
      expect(savePublicPageSettings).toHaveBeenCalledWith({
        hide_best_times: false, hide_progression: true, hide_comparison: false,
        links: ["https://strava.com/athletes/1"], pinned_participation_id: 5,
      }),
    );
    await waitFor(() => expect(annonce).toHaveTextContent("Réglages enregistrés."));
  });

  it("shows the server message on a refused link", async () => {
    savePublicPageSettings.mockRejectedValue(new ApiError(422, "Ce lien n'est pas accepté."));
    afficher();

    await userEvent.click(await screen.findByRole("button", { name: "Enregistrer" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Ce lien n'est pas accepté.");
  });

  it("shows an inline error, without crashing, when the settings cannot be loaded", async () => {
    getPublicPageSettings.mockRejectedValue(new ApiError(500, "Réglages indisponibles."));
    afficher();

    expect(screen.getByRole("heading", { name: "Ma fiche publique" })).toBeInTheDocument();
    expect(await screen.findByRole("alert")).toHaveTextContent("Réglages indisponibles. Rechargez la page, ou réessayez dans un instant.");
    expect(screen.queryByRole("button", { name: "Enregistrer" })).toBeNull();
  });

  it("keeps its titled card busy while the settings load", () => {
    getPublicPageSettings.mockReturnValue(new Promise(() => {}));
    afficher();

    expect(screen.getByRole("heading", { name: "Ma fiche publique" }).closest("[aria-busy]")).toHaveAttribute("aria-busy", "true");
  });

  it("locks the pin choice while the results load, and says so when they fail", async () => {
    getPublicPageSettings.mockResolvedValue({ ...REGLAGES, pinned_participation_id: 5 });
    let echouer: (e: Error) => void = () => {};
    getAthlete.mockReturnValue(new Promise((_, reject) => { echouer = reject; }));
    afficher();

    const choix = await screen.findByLabelText("Résultat épinglé");
    expect(choix).toBeDisabled();
    echouer(new ApiError(500, "Fiche indisponible."));
    expect(await screen.findByText("Vos résultats n'ont pas pu être chargés : le résultat épinglé reste inchangé.")).toBeInTheDocument();
    expect(choix).toBeDisabled();
  });

  it("names each link field once and points to the accepted sites", async () => {
    afficher();

    const champ = await screen.findByLabelText("Lien 1");
    expect(champ).toHaveAccessibleDescription("Profils Strava, Garmin Connect, Polar Flow ou Suunto, en https.");
  });

  it("warns when several accounts share the fiche", async () => {
    getPublicPageSettings.mockResolvedValue({ ...REGLAGES, shared: true });
    afficher();

    expect(await screen.findByText("Plusieurs comptes sont rattachés à votre fiche : vos liens, votre objectif et votre résultat épinglé n'y sont pas affichés.")).toBeInTheDocument();
  });
});
