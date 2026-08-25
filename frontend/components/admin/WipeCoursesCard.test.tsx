import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiError } from "@/lib/api/client";
import type { SessionUser } from "@/lib/types";

const { getCoursesWipeImpact, wipeAllCourses, getSession, toastError, toastSuccess } = vi.hoisted(
  () => ({
    getCoursesWipeImpact: vi.fn(),
    wipeAllCourses: vi.fn(),
    getSession: vi.fn(),
    toastError: vi.fn(),
    toastSuccess: vi.fn(),
  }),
);

vi.mock("sonner", () => ({ toast: { error: toastError, success: toastSuccess } }));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: { getCoursesWipeImpact, wipeAllCourses, getSession },
  };
});

import { WipeCoursesCard } from "./WipeCoursesCard";

function session(permissions: string[]): SessionUser {
  return {
    id: 1,
    email: "admin@exemple.fr",
    display_name: "Admin",
    created_at: "2026-01-01T00:00:00Z",
    permissions,
    roles: [],
    groups: [],
  };
}

let client: QueryClient;

function afficher() {
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <WipeCoursesCard />
    </QueryClientProvider>,
  );
}

describe("WipeCoursesCard (#384, suite)", () => {
  beforeEach(() => {
    getCoursesWipeImpact.mockReset();
    wipeAllCourses.mockReset();
    getSession.mockReset();
    toastError.mockReset();
    toastSuccess.mockReset();
  });

  it("reste invisible sans le pouvoir", async () => {
    getSession.mockResolvedValue(session([]));

    afficher();

    await waitFor(() => expect(client.getQueryState(["session"])?.status).toBe("success"));
    expect(screen.queryByText(/repartir de zéro/i)).not.toBeInTheDocument();
  });

  it("propose le geste au porteur du pouvoir", async () => {
    getSession.mockResolvedValue(session(["courses:wipe_all"]));

    afficher();

    expect(await screen.findByText(/repartir de zéro/i)).toBeInTheDocument();
  });

  it("ne chiffre rien tant que la modale n'est pas ouverte", async () => {
    getSession.mockResolvedValue(session(["courses:wipe_all"]));
    getCoursesWipeImpact.mockResolvedValue({ courses: 53, participations: 412, athletes: 37 });

    afficher();
    const ouvrir = await screen.findByRole("button", { name: /supprimer toutes les épreuves/i });

    expect(getCoursesWipeImpact).not.toHaveBeenCalled();

    await userEvent.click(ouvrir);

    await waitFor(() => expect(getCoursesWipeImpact).toHaveBeenCalled());
  });

  it.each([
    [1, 1, 1, /1 épreuve sera détruite/, /1 résultat sera détruit/, /1 fiche coureur sera retirée/],
    [
      0,
      0,
      0,
      /0 épreuves seront détruites/,
      /0 résultats seront détruits/,
      /0 fiches coureur seront retirées/,
    ],
    [
      53,
      412,
      37,
      /53 épreuves seront détruites/,
      /412 résultats seront détruits/,
      /37 fiches coureur seront retirées/,
    ],
  ])(
    "accorde le verbe avec le nombre annoncé (%i, %i, %i)",
    async (courses, participations, athletes, phraseCourses, phraseResultats, phraseCoureurs) => {
      getSession.mockResolvedValue(session(["courses:wipe_all"]));
      getCoursesWipeImpact.mockResolvedValue({ courses, participations, athletes });

      afficher();
      await userEvent.click(
        await screen.findByRole("button", { name: /supprimer toutes les épreuves/i }),
      );

      const annonce = await screen.findByRole("list");
      expect(annonce).toHaveTextContent(phraseCourses);
      expect(annonce).toHaveTextContent(phraseResultats);
      expect(annonce).toHaveTextContent(phraseCoureurs);
    },
  );

  it("n'active pas la purge quand le chiffrage échoue", async () => {
    getSession.mockResolvedValue(session(["courses:wipe_all"]));
    getCoursesWipeImpact.mockRejectedValue(new ApiError(500, "Panne"));

    afficher();
    await userEvent.click(
      await screen.findByRole("button", { name: /supprimer toutes les épreuves/i }),
    );

    expect(await screen.findByText(/ampleur.*n'a pas pu être chiffrée/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /supprimer définitivement/i })).toBeDisabled();
  });

  it("le bouton de confirmation reste désactivé sans avoir tapé SUPPRIMER", async () => {
    getSession.mockResolvedValue(session(["courses:wipe_all"]));
    getCoursesWipeImpact.mockResolvedValue({ courses: 53, participations: 412, athletes: 37 });

    afficher();
    await userEvent.click(
      await screen.findByRole("button", { name: /supprimer toutes les épreuves/i }),
    );
    await screen.findByText(/412/);

    expect(screen.getByRole("button", { name: /supprimer définitivement/i })).toBeDisabled();
  });

  it("s'active une fois SUPPRIMER tapé, et purge à la confirmation en annonçant le décompte réel", async () => {
    getSession.mockResolvedValue(session(["courses:wipe_all"]));
    getCoursesWipeImpact.mockResolvedValue({ courses: 53, participations: 412, athletes: 37 });
    wipeAllCourses.mockResolvedValue({ courses_deleted: 53, athletes_purged: 37 });

    afficher();
    await userEvent.click(
      await screen.findByRole("button", { name: /supprimer toutes les épreuves/i }),
    );
    await screen.findByText(/412/);
    await userEvent.type(screen.getByLabelText(/tapez/i), "SUPPRIMER");

    await userEvent.click(screen.getByRole("button", { name: /supprimer définitivement/i }));

    await waitFor(() => expect(wipeAllCourses).toHaveBeenCalled());
    expect(toastSuccess).toHaveBeenCalledWith(
      "53 épreuves supprimées, 37 fiches coureur purgées.",
    );
  });

  it("une saisie approximative ne suffit pas", async () => {
    getSession.mockResolvedValue(session(["courses:wipe_all"]));
    getCoursesWipeImpact.mockResolvedValue({ courses: 53, participations: 412, athletes: 37 });

    afficher();
    await userEvent.click(
      await screen.findByRole("button", { name: /supprimer toutes les épreuves/i }),
    );
    await screen.findByText(/412/);
    await userEvent.type(screen.getByLabelText(/tapez/i), "supprimer");

    expect(screen.getByRole("button", { name: /supprimer définitivement/i })).toBeDisabled();
  });

  it("dit en français qu'un refus de droits a bloqué la purge", async () => {
    getSession.mockResolvedValue(session(["courses:wipe_all"]));
    getCoursesWipeImpact.mockResolvedValue({ courses: 3, participations: 5, athletes: 1 });
    wipeAllCourses.mockRejectedValue(new ApiError(403, "Vous n'avez pas les droits nécessaires."));

    afficher();
    await userEvent.click(
      await screen.findByRole("button", { name: /supprimer toutes les épreuves/i }),
    );
    await screen.findByText(/^5$/);
    await userEvent.type(screen.getByLabelText(/tapez/i), "SUPPRIMER");
    await userEvent.click(screen.getByRole("button", { name: /supprimer définitivement/i }));

    await waitFor(() =>
      expect(toastError).toHaveBeenCalledWith("Vous n'avez pas les droits nécessaires."),
    );
  });

  it("oublie le mot tapé si on renonce puis rouvre", async () => {
    getSession.mockResolvedValue(session(["courses:wipe_all"]));
    getCoursesWipeImpact.mockResolvedValue({ courses: 53, participations: 412, athletes: 37 });

    afficher();
    await userEvent.click(await screen.findByRole("button", { name: /Supprimer toutes les épreuves/ }));
    await userEvent.type(await screen.findByLabelText(/Tapez/), "SUPPRIMER");
    await userEvent.click(screen.getByRole("button", { name: "Renoncer" }));
    await userEvent.click(await screen.findByRole("button", { name: /Supprimer toutes les épreuves/ }));
    expect(
      (await screen.findByRole("button", { name: "Supprimer définitivement" })).hasAttribute("disabled"),
    ).toBe(true);
  });

  it("n'offre aucune annulation : le geste est irréversible", async () => {
    getSession.mockResolvedValue(session(["courses:wipe_all"]));
    getCoursesWipeImpact.mockResolvedValue({ courses: 3, participations: 3, athletes: 1 });

    afficher();
    await userEvent.click(
      await screen.findByRole("button", { name: /supprimer toutes les épreuves/i }),
    );

    expect(await screen.findByText(/irréversible/i)).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /annuler la purge|rétablir|restaurer/i }),
    ).not.toBeInTheDocument();
  });
});
