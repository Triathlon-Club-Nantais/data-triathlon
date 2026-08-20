import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api/client";

const { getSession, listAuthMethods, redirect } = vi.hoisted(() => ({
  getSession: vi.fn(),
  listAuthMethods: vi.fn(),
  redirect: vi.fn(() => {
    // `redirect()` de Next interrompt le rendu en levant : le simuler à
    // l'identique est ce qui prouve que rien n'est rendu après la garde.
    throw new Error("NEXT_REDIRECT");
  }),
}));

vi.mock("@/lib/api/server", () => ({
  apiServer: { getSession, listAuthMethods },
}));
vi.mock("next/navigation", () => ({ redirect }));

import AdminLayout from "./layout";

const SESSION = {
  id: 1,
  email: "contributeur@exemple.fr",
  display_name: "contributeur",
  created_at: "2026-08-01T14:54:28Z",
  permissions: ["courses:delete"],
  roles: [],
};

/** Connecté, mais ne portant aucun pouvoir du catalogue (#115). */
const SANS_POUVOIR = { ...SESSION, permissions: [] };

const GITHUB = [{ slug: "github", label: "GitHub" }];

describe("Garde des écrans d'administration (FR-040)", () => {
  // Sans cela, `expect(redirect).not.toHaveBeenCalled()` mesurerait les appels
  // des tests précédents — et passerait, ou échouerait, pour la mauvaise raison.
  let journal: ReturnType<typeof vi.spyOn>;
  beforeEach(() => {
    vi.clearAllMocks();
    // Les cas de panne journalisent volontairement : capturé plutôt qu'affiché,
    // sinon la sortie des tests ressemble à une suite en échec.
    journal = vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    journal.mockRestore();
  });

  it("redirige vers /login sans session, quand la connexion est possible", async () => {
    getSession.mockResolvedValue(null);
    listAuthMethods.mockResolvedValue(GITHUB);

    await expect(AdminLayout({ children: <p>secret</p> })).rejects.toThrow("NEXT_REDIRECT");
    expect(redirect).toHaveBeenCalledWith("/login");
  });

  it("rend les enfants avec une session valide", async () => {
    getSession.mockResolvedValue(SESSION);
    listAuthMethods.mockResolvedValue(GITHUB);

    render(await AdminLayout({ children: <p>contenu réservé</p> }));

    expect(screen.getByText("contenu réservé")).toBeInTheDocument();
  });

  it("renvoie au tableau de bord une session sans le moindre pouvoir", async () => {
    // Le catalogue de #115 ne contient que des pouvoirs d'administration : n'en
    // porter aucun, c'est n'avoir rien à faire ici. Vers `/dashboard` et non
    // `/login`, qui serait une boucle pour quelqu'un de déjà connecté.
    getSession.mockResolvedValue(SANS_POUVOIR);
    listAuthMethods.mockResolvedValue(GITHUB);

    await expect(AdminLayout({ children: <p>secret</p> })).rejects.toThrow("NEXT_REDIRECT");
    expect(redirect).toHaveBeenCalledWith("/dashboard");
  });

  it("valide réellement la session, plutôt que de constater un cookie", async () => {
    // Un `middleware.ts` ne peut voir que la **présence** du cookie : il
    // laisserait passer une session révoquée ou expirée.
    getSession.mockResolvedValue(null);
    listAuthMethods.mockResolvedValue(GITHUB);

    await expect(AdminLayout({ children: <p>secret</p> })).rejects.toThrow();
    expect(getSession).toHaveBeenCalled();
  });

  it("laisse passer quand aucune connexion n'est possible (FR-036)", async () => {
    // Sans les secrets `AUTH_*` — l'état de tout déploiement tant qu'un
    // opérateur ne les a pas posés, `render.yaml` les déclarant `sync: false` —
    // `/auth/me` rend 401 pour tout le monde. Rediriger ferait de `/admin`,
    // écran ouvert jusqu'ici, une impasse pour **tous** : la garde est
    // d'interface, elle ne doit pas fermer ce qu'elle ne protège pas.
    getSession.mockResolvedValue(null);
    listAuthMethods.mockResolvedValue([]);

    render(await AdminLayout({ children: <p>contenu réservé</p> }));

    expect(screen.getByText("contenu réservé")).toBeInTheDocument();
    expect(redirect).not.toHaveBeenCalled();
  });

  it("laisse passer quand le backend est en panne", async () => {
    // Un démarrage à froid de Render ne doit pas remplacer l'écran par la page
    // d'erreur globale : avant cette garde, `/admin` s'affichait et c'est le
    // tableau client qui signalait la panne dans la page.
    getSession.mockRejectedValue(new ApiError(502, "Erreur API (502)"));
    listAuthMethods.mockResolvedValue(GITHUB);

    render(await AdminLayout({ children: <p>contenu réservé</p> }));

    expect(screen.getByText("contenu réservé")).toBeInTheDocument();
    expect(redirect).not.toHaveBeenCalled();
  });

  it("nomme la panne au journal, statut compris", async () => {
    // Les deux pannes appellent la même conduite mais pas le même diagnostic :
    // un 502 est un backend injoignable, un 500 sur `/auth/me` est notre propre
    // route qui plante. Sans la trace, la garde se dégrade en silence.
    getSession.mockRejectedValue(new ApiError(500, "Boum"));
    listAuthMethods.mockResolvedValue(GITHUB);

    render(await AdminLayout({ children: <p>contenu réservé</p> }));

    expect(journal).toHaveBeenCalledWith(expect.stringContaining("session indisponible (500)"));
  });

  it("dit « sans réponse » quand l'échec ne porte aucun statut", async () => {
    // Une coupure réseau ne produit pas d'`ApiError` : le journal doit le dire
    // plutôt qu'inventer un code HTTP.
    getSession.mockRejectedValue(new TypeError("fetch failed"));
    listAuthMethods.mockResolvedValue(GITHUB);

    render(await AdminLayout({ children: <p>contenu réservé</p> }));

    expect(journal).toHaveBeenCalledWith(
      expect.stringContaining("session indisponible (sans réponse)"),
    );
  });

  it("laisse passer quand la liste des méthodes est elle-même injoignable", async () => {
    getSession.mockResolvedValue(null);
    listAuthMethods.mockRejectedValue(new Error("Erreur API (502)"));

    render(await AdminLayout({ children: <p>contenu réservé</p> }));

    expect(screen.getByText("contenu réservé")).toBeInTheDocument();
  });
});
