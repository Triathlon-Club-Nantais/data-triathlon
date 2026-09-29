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
import { useSiteAccessOpen } from "@/components/site-access/site-access-open";

function SondeAccesOuvert() {
  return <span data-testid="sonde">{String(useSiteAccessOpen())}</span>;
}

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

  // #1057 : le geste « Oublier le code d'accès » du pied de page ne se montre
  // que là où le code a été accepté, jamais sous le formulaire du code.
  it.each([
    ["accès avéré", () => checkSiteAccess.mockResolvedValue(true), true],
    ["refus", () => checkSiteAccess.mockResolvedValue(false), false],
    ["panne", () => checkSiteAccess.mockRejectedValue(new ApiError(502, "x")), false],
  ])("n'ouvre le geste d'oubli du code que sur un %s", async (_cas, preparer, attendu) => {
    preparer();

    render(
      <>
        {await ProtegeLayout({ children: <p>contenu réservé</p> })}
        <SondeAccesOuvert />
      </>,
    );

    expect(screen.getByTestId("sonde").textContent).toBe(String(attendu));
  });

  it("propose un lien discret vers le guide (#865, #878), hors du rail de navigation", async () => {
    // Retiré de `nav.config.ts` par #878 : même arbitrage que le guide admin
    // (`app/admin/layout.tsx`), pour ne pas concurrencer les vraies
    // destinations sur l'entrée la plus fréquentée de la nav.
    checkSiteAccess.mockResolvedValue(true);

    render(await ProtegeLayout({ children: <p>contenu réservé</p> }));

    expect(screen.getByRole("link", { name: /guide/i })).toHaveAttribute("href", "/guide");
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
