import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

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
};

const GITHUB = [{ slug: "github", label: "GitHub" }];

describe("Garde des écrans d'administration (FR-040)", () => {
  // Sans cela, `expect(redirect).not.toHaveBeenCalled()` mesurerait les appels
  // des tests précédents — et passerait, ou échouerait, pour la mauvaise raison.
  beforeEach(() => {
    vi.clearAllMocks();
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
    getSession.mockRejectedValue(new Error("Erreur API (502)"));
    listAuthMethods.mockResolvedValue(GITHUB);

    render(await AdminLayout({ children: <p>contenu réservé</p> }));

    expect(screen.getByText("contenu réservé")).toBeInTheDocument();
    expect(redirect).not.toHaveBeenCalled();
  });

  it("laisse passer quand la liste des méthodes est elle-même injoignable", async () => {
    getSession.mockResolvedValue(null);
    listAuthMethods.mockRejectedValue(new Error("Erreur API (502)"));

    render(await AdminLayout({ children: <p>contenu réservé</p> }));

    expect(screen.getByText("contenu réservé")).toBeInTheDocument();
  });
});
