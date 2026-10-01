import { describe, it, expect } from "vitest";
import { ApiError } from "@/lib/api/client";
import { messageDeRefus } from "@/lib/api/refus";

const GROUPES = { sujet: "groupes", action: "consulter les groupes d'appartenance" };

describe("messageDeRefus", () => {
  it("distingue la session expirée du refus de droit", () => {
    expect(messageDeRefus(new ApiError(401, "Non connecté"), GROUPES)).toEqual({
      title: "Session expirée",
      description: "Reconnectez-vous pour consulter les groupes.",
    });
  });

  // #877 : un admin connecté sans cookie de site lisait « Session expirée ».
  it("distingue le code d'accès au site manquant de la session expirée", () => {
    const erreur = new ApiError(401, "Code d'accès au site requis.", null, {}, "site_access_required");

    const message = messageDeRefus(erreur, GROUPES);

    expect(message.title).toBe("Code d'accès requis");
    expect(message.description).toBe(
      "Le code d'accès au site manque ou a expiré. Saisissez-le pour consulter les groupes.",
    );
    // Un texte seul ne mène nulle part : le refus porte le lien vers la saisie.
    expect(message.action).toBeDefined();
  });

  it("nomme le geste refusé et la façon de l'obtenir", () => {
    const message = messageDeRefus(new ApiError(403, "Refusé"), GROUPES);

    expect(message.title).toBe("Accès refusé");
    expect(message.description).toBe(
      "Votre rôle ne permet pas de consulter les groupes d'appartenance. " +
        "Demandez le pouvoir correspondant à un administrateur.",
    );
  });

  it("retombe sur la panne pour tout autre statut", () => {
    expect(messageDeRefus(new ApiError(500, "Boum"), GROUPES)).toEqual({
      title: "Liste indisponible",
      description: "Les groupes n'ont pas pu être chargés. Réessayez plus tard.",
    });
  });

  it("retombe sur la panne pour une erreur sans statut", () => {
    // Une coupure réseau rend une `Error` nue : elle ne dit rien du droit, et
    // l'écran ne doit surtout pas conclure au refus.
    expect(messageDeRefus(new Error("Failed to fetch"), GROUPES).title).toBe(
      "Liste indisponible",
    );
  });
});
