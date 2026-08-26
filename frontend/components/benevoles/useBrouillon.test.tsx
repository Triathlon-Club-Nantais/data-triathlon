import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import type { AthleteBrief, Participation } from "@/lib/types";

const {
  renameCourseBenevole,
  updateParticipationFieldsBenevole,
  reassignParticipationBenevole,
  validateParticipationBenevole,
} = vi.hoisted(() => ({
  renameCourseBenevole: vi.fn(),
  updateParticipationFieldsBenevole: vi.fn(),
  reassignParticipationBenevole: vi.fn(),
  validateParticipationBenevole: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: {
      renameCourseBenevole,
      updateParticipationFieldsBenevole,
      reassignParticipationBenevole,
      validateParticipationBenevole,
    },
  };
});

import { ApiError } from "@/lib/api/client";
import { useBrouillon } from "./useBrouillon";

const ATHLETE: AthleteBrief = { id: 1, nom: "HERRMANN", prenom: "Mathieu", gender: "M", club: "TCN" };
const AUTRE: AthleteBrief = { id: 2, nom: "KERMARREC", prenom: "Hadrien", gender: "M", club: "TCN" };

function participation(over: Partial<Participation> = {}): Participation {
  return {
    id: 10,
    athlete: ATHLETE,
    course: {
      id: 99,
      name: "Triathlon de Nantes",
      event_date: "2026-06-14",
      event_type: "triathlon",
      provider: "njuko",
      source_url: "https://example.test/r",
      is_relay: false,
    },
    club: "TCN",
    is_tcn: true,
    category: "V2 M",
    bib_number: "412",
    rank_overall: 37,
    rank_category: null,
    rank_gender: null,
    total_time: "02:14:53",
    status: "finisher",
    is_relay: false,
    splits: null,
    created_at: null,
    is_pending_validation: true,
    ...over,
  };
}

function monter(p = participation()) {
  const onChanged = vi.fn();
  const onSessionExpired = vi.fn();
  const rendu = renderHook(() => useBrouillon(p, { onChanged, onSessionExpired }));
  return { ...rendu, onChanged, onSessionExpired, participation: p };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("useBrouillon", () => {
  it("part propre et devient sale à la première modification", () => {
    const { result } = monter();
    expect(result.current.sale).toBe(false);
    act(() => result.current.modifier({ bib_number: "413" }));
    expect(result.current.sale).toBe(true);
  });

  it("n'appelle rien quand rien n'a bougé", async () => {
    const { result } = monter();
    await act(async () => {
      expect(await result.current.enregistrer()).toBe(true);
    });
    expect(updateParticipationFieldsBenevole).not.toHaveBeenCalled();
  });

  it("n'appelle que la route dont les champs ont bougé", async () => {
    const { result, onChanged } = monter();
    updateParticipationFieldsBenevole.mockResolvedValue(participation({ bib_number: "413" }));

    act(() => result.current.modifier({ bib_number: "413" }));
    await act(async () => void (await result.current.enregistrer()));

    expect(updateParticipationFieldsBenevole).toHaveBeenCalledWith(10, { bib_number: "413" });
    expect(renameCourseBenevole).not.toHaveBeenCalled();
    expect(reassignParticipationBenevole).not.toHaveBeenCalled();
    expect(onChanged).toHaveBeenCalledWith(participation({ bib_number: "413" }));
    expect(result.current.sale).toBe(false);
  });

  it("enchaîne renommage, champs et réattribution dans cet ordre", async () => {
    const { result } = monter();
    const ordre: string[] = [];
    renameCourseBenevole.mockImplementation(async () => {
      ordre.push("nom");
      return { ...participation().course, name: "Nouveau nom" };
    });
    updateParticipationFieldsBenevole.mockImplementation(async () => {
      ordre.push("champs");
      return participation({ bib_number: "413" });
    });
    reassignParticipationBenevole.mockImplementation(async () => {
      ordre.push("reattribution");
      return participation({ athlete: AUTRE, bib_number: "413" });
    });

    act(() =>
      result.current.modifier({ nom_epreuve: "Nouveau nom", bib_number: "413", athlete_cible: AUTRE }),
    );
    await act(async () => void (await result.current.enregistrer()));

    expect(ordre).toEqual(["nom", "champs", "reattribution"]);
  });

  it("garde sale ce qui n'a pas pu partir après un échec partiel", async () => {
    const { result, onChanged } = monter();
    renameCourseBenevole.mockResolvedValue({ ...participation().course, name: "Nouveau nom" });
    updateParticipationFieldsBenevole.mockRejectedValue(new ApiError(409, "Ce dossard est déjà pris."));

    act(() => result.current.modifier({ nom_epreuve: "Nouveau nom", bib_number: "413" }));
    await act(async () => {
      expect(await result.current.enregistrer()).toBe(false);
    });

    expect(result.current.erreur).toBe(
      "Les champs n'ont pas pu être enregistrés : Ce dossard est déjà pris.",
    );
    expect(result.current.brouillon.nom_epreuve).toBe("Nouveau nom");
    expect(result.current.brouillon.bib_number).toBe("413");
    expect(result.current.sale).toBe(true);
    // Le renommage est commité : le parent le sait, même si l'ensemble a échoué.
    expect(onChanged).toHaveBeenCalled();
  });

  it("refuse d'enregistrer une saisie invalide sans appeler le réseau", async () => {
    const { result } = monter();
    act(() => result.current.modifier({ nom_epreuve: "   " }));
    await act(async () => {
      expect(await result.current.enregistrer()).toBe(false);
    });
    expect(result.current.erreur).toBe("Le nom de l'épreuve ne peut pas être vide.");
    expect(renameCourseBenevole).not.toHaveBeenCalled();
  });

  it("enregistre d'abord, puis valide", async () => {
    const { result } = monter();
    const ordre: string[] = [];
    updateParticipationFieldsBenevole.mockImplementation(async () => {
      ordre.push("champs");
      return participation({ bib_number: "413" });
    });
    validateParticipationBenevole.mockImplementation(async () => {
      ordre.push("validation");
      return participation({ bib_number: "413", is_pending_validation: false });
    });

    act(() => result.current.modifier({ bib_number: "413" }));
    await act(async () => void (await result.current.validerLeResultat()));

    expect(ordre).toEqual(["champs", "validation"]);
  });

  it("abandonne la validation quand l'enregistrement échoue", async () => {
    const { result } = monter();
    updateParticipationFieldsBenevole.mockRejectedValue(new ApiError(409, "Ce dossard est déjà pris."));

    act(() => result.current.modifier({ bib_number: "413" }));
    await act(async () => void (await result.current.validerLeResultat()));

    expect(validateParticipationBenevole).not.toHaveBeenCalled();
    expect(result.current.erreur).toContain("Ce dossard est déjà pris.");
  });

  it("prévient d'une session expirée plutôt que d'afficher une erreur générique", async () => {
    const { result, onSessionExpired } = monter();
    updateParticipationFieldsBenevole.mockRejectedValue(new ApiError(401, "non autorisé"));

    act(() => result.current.modifier({ bib_number: "413" }));
    await act(async () => void (await result.current.enregistrer()));

    await waitFor(() => expect(onSessionExpired).toHaveBeenCalled());
    expect(result.current.erreur).toBeNull();
  });

  it("valide un brouillon propre et propage le résultat", async () => {
    const { result, onChanged } = monter();
    const validee = participation({ is_pending_validation: false });
    validateParticipationBenevole.mockResolvedValue(validee);

    await act(async () => void (await result.current.validerLeResultat()));

    expect(validateParticipationBenevole).toHaveBeenCalledWith(10);
    expect(onChanged).toHaveBeenCalledWith(validee);
    expect(updateParticipationFieldsBenevole).not.toHaveBeenCalled();
  });

  it("prévient d'une session expirée quand la validation elle-même échoue en 401", async () => {
    const { result, onSessionExpired } = monter();
    validateParticipationBenevole.mockRejectedValue(new ApiError(401, "non autorisé"));

    await act(async () => void (await result.current.validerLeResultat()));

    await waitFor(() => expect(onSessionExpired).toHaveBeenCalled());
    expect(result.current.erreur).toBeNull();
  });

  it("affiche l'erreur quand la validation elle-même échoue hors 401", async () => {
    const { result } = monter();
    validateParticipationBenevole.mockRejectedValue(new ApiError(409, "Ce résultat a déjà été validé."));

    await act(async () => void (await result.current.validerLeResultat()));

    expect(result.current.erreur).toBe("Ce résultat a déjà été validé.");
  });

  it("distingue la validation de l'enregistrement pendant le geste le plus fréquent : valider un brouillon propre", async () => {
    // Sur un brouillon propre, `enregistrer()` ressort immédiatement sans
    // toucher `enCours` — seul l'appel de validation tourne. Avant #490
    // (revue de branche finale), rien ne distinguait ce cas de
    // l'enregistrement des champs, et le bouton affichait « Enregistrement… »
    // pour un appel qui ne fait que valider.
    const { result } = monter();
    let resoudre!: (p: Participation) => void;
    validateParticipationBenevole.mockReturnValue(
      new Promise<Participation>((resolve) => {
        resoudre = resolve;
      }),
    );

    let promesse!: Promise<void>;
    act(() => {
      promesse = result.current.validerLeResultat();
    });

    await waitFor(() => expect(result.current.validationEnCours).toBe(true));
    expect(result.current.enCours).toBe(true);

    await act(async () => {
      resoudre(participation({ is_pending_validation: false }));
      await promesse;
    });

    expect(result.current.validationEnCours).toBe(false);
    expect(result.current.enCours).toBe(false);
  });
});
