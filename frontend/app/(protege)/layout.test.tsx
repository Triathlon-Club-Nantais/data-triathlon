import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api/client";

const { checkSiteAccess, redirect } = vi.hoisted(() => ({
  checkSiteAccess: vi.fn(),
  redirect: vi.fn(() => {
    // `redirect()` de Next interrompt le rendu en levant : le simuler à
    // l'identique est ce qui prouve que rien n'est rendu après la garde.
    throw new Error("NEXT_REDIRECT");
  }),
}));

vi.mock("@/lib/api/server", () => ({
  apiServer: { checkSiteAccess },
}));
vi.mock("next/navigation", () => ({ redirect }));

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
    expect(redirect).not.toHaveBeenCalled();
  });

  it("redirige vers /acces sur un 401 avéré (cookie absent ou invalide)", async () => {
    checkSiteAccess.mockResolvedValue(false);

    await expect(ProtegeLayout({ children: <p>secret</p> })).rejects.toThrow("NEXT_REDIRECT");
    expect(redirect).toHaveBeenCalledWith("/acces");
  });

  it("laisse passer quand le backend est en panne (erreur réseau)", async () => {
    // Une coupure réseau ne produit pas d'`ApiError` : ce n'est pas un 401
    // avéré, donc pas un refus — fermer le site pendant une panne backend
    // serait pire que l'ouvrir (Fix #2 de la revue finale).
    checkSiteAccess.mockRejectedValue(new TypeError("fetch failed"));

    render(await ProtegeLayout({ children: <p>contenu réservé</p> }));

    expect(screen.getByText("contenu réservé")).toBeInTheDocument();
    expect(redirect).not.toHaveBeenCalled();
    expect(journal).toHaveBeenCalledWith(
      expect.stringContaining("session indisponible (sans réponse)"),
    );
  });

  it("laisse passer sur une réponse ≠ 200/401 (5xx, démarrage à froid)", async () => {
    checkSiteAccess.mockRejectedValue(new ApiError(502, "Erreur API (502)"));

    render(await ProtegeLayout({ children: <p>contenu réservé</p> }));

    expect(screen.getByText("contenu réservé")).toBeInTheDocument();
    expect(redirect).not.toHaveBeenCalled();
    expect(journal).toHaveBeenCalledWith(expect.stringContaining("session indisponible (502)"));
  });
});
