import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api/client";

const { checkSiteAccess } = vi.hoisted(() => ({ checkSiteAccess: vi.fn() }));

vi.mock("@/lib/api/server", () => ({
  apiServer: { checkSiteAccess },
}));
vi.mock("@/components/site-access/SiteAccessGate", () => ({
  SiteAccessGate: () => <p>formulaire de mot de passe</p>,
}));

import ProtegeLayout from "./layout";

describe("Garde d'accès au site (#509)", () => {
  // Sans cela, `expect(redirect).not.toHaveBeenCalled()` mesurerait les appels
  // des tests précédents — et passerait, ou échouerait, pour la mauvaise raison.
  let journal: ReturnType<typeof vi.spyOn>;
  beforeEach(() => {
    vi.clearAllMocks();
    // Le cas de panne journalise volontairement : capturé plutôt qu'affiché,
    // sinon la sortie des tests ressemble à une suite en échec.
    journal = vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    journal.mockRestore();
  });

  it("rend les enfants avec une session valide", async () => {
    checkSiteAccess.mockResolvedValue(true);

    render(await ProtegeLayout({ children: <p>contenu réservé</p> }));

    expect(screen.getByText("contenu réservé")).toBeInTheDocument();
    expect(screen.queryByText("formulaire de mot de passe")).not.toBeInTheDocument();
  });

  it("rend le formulaire **à la place** des enfants sur un 401 avéré", async () => {
    // Et non une redirection vers `/acces` : un layout serveur ne connaît pas
    // le chemin demandé (Next n'expose ni `pathname` ni `searchParams` à un
    // layout), donc la redirection perdait la destination — quelqu'un qui suit
    // un lien vers `/courses/42` atterrissait sur le tableau de bord (relevé en
    // revue de #513). Rendu sur place, l'URL ne bouge pas : il n'y a plus de
    // destination à transporter, et pas de paramètre `next` à valider contre la
    // redirection ouverte.
    checkSiteAccess.mockResolvedValue(false);

    render(await ProtegeLayout({ children: <p>secret</p> }));

    expect(screen.getByText("formulaire de mot de passe")).toBeInTheDocument();
    expect(screen.queryByText("secret")).not.toBeInTheDocument();
  });

  it("laisse passer quand le backend est en panne (erreur réseau)", async () => {
    // Une coupure réseau ne produit pas d'`ApiError` : ce n'est pas un 401
    // avéré, donc pas un refus — fermer le site pendant une panne backend
    // serait pire que l'ouvrir (Fix #2 de la revue finale).
    checkSiteAccess.mockRejectedValue(new TypeError("fetch failed"));

    render(await ProtegeLayout({ children: <p>contenu réservé</p> }));

    expect(screen.getByText("contenu réservé")).toBeInTheDocument();
    expect(screen.queryByText("formulaire de mot de passe")).not.toBeInTheDocument();
    expect(journal).toHaveBeenCalledWith(
      expect.stringContaining("session indisponible (sans réponse)"),
    );
  });

  it("laisse passer sur une réponse ≠ 200/401 (5xx, démarrage à froid)", async () => {
    checkSiteAccess.mockRejectedValue(new ApiError(502, "Erreur API (502)"));

    render(await ProtegeLayout({ children: <p>contenu réservé</p> }));

    expect(screen.getByText("contenu réservé")).toBeInTheDocument();
    expect(screen.queryByText("formulaire de mot de passe")).not.toBeInTheDocument();
    expect(journal).toHaveBeenCalledWith(expect.stringContaining("session indisponible (502)"));
  });
});
