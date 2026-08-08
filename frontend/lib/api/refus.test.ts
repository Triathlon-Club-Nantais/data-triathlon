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
