import { describe, it, expect, vi, beforeEach } from "vitest";
import { act, render, screen, waitFor, fireEvent, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { HeatFailure, ImportedCourse } from "@/lib/types";

// Ces tests contrôlent l'état du hook d'import de bout en bout pour n'observer
// que le rendu — l'objectif est de câbler la phase `done` sur /courses/{id} (#135)
// et le rafraîchissement RSC (#201). Le repli « échec → saisie manuelle », lui,
// vivait dans `ScrapeForm.test` : ce fichier a été supprimé avec le composant
// qu'il testait, le repli est resté, son test l'a suivi ici.
const importMock = vi.hoisted(() => {
  let state = {
    running: false,
    phase: "idle" as string,
    message: "",
    total: 0,
    progress: 0,
    imported: 0,
    updated: 0,
    skipped: 0,
    cached: false,
    courses: [] as ImportedCourse[],
    heatsEnumerated: 0,
    heatsImported: 0,
    heatsCached: 0,
    heatsFailed: 0,
    failures: [] as HeatFailure[],
    error: null as string | null,
    errorStatus: null as number | null,
    retryAfter: null as number | null,
    heatIndex: 0,
    heatsScrapingTotal: 0,
    heatLabel: "",
    detailDone: 0,
    detailTotal: 0,
  };
  return {
    start: vi.fn(),
    cancel: vi.fn(),
    reset: vi.fn(),
    get: () => state,
    set: (patch: Partial<typeof state>) => {
      state = { ...state, ...patch };
    },
  };
});

vi.mock("@/hooks/useImportStream", () => ({
  useImportStream: () => ({
    state: importMock.get(),
    start: importMock.start,
    cancel: importMock.cancel,
    reset: importMock.reset,
  }),
}));

const refreshMock = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: refreshMock, push: vi.fn() }),
}));

vi.mock("@/lib/api/client", () => ({
  apiClient: {
    detectProvider: vi.fn().mockResolvedValue({ provider: "klikego", supported: true }),
    listProviders: vi.fn().mockResolvedValue(["klikego", "wiclax"]),
    reportPendingProvider: vi.fn().mockResolvedValue({}),
    saveParticipation: vi.fn().mockResolvedValue({}),
  },
}));

vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn(), message: vi.fn() } }));

import { TcnScrapeForm } from "./TcnScrapeForm";
import { apiClient } from "@/lib/api/client";
import { toast } from "sonner";

/** Le champ URL, désigné par son nom accessible — le placeholder n'en est pas
 *  un, et il disparaît dès que « Coller » remplit le champ. */
const champUrl = () => screen.getByRole("textbox", { name: /Adresse des résultats/ });

function renderForm() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const utils = render(
    <QueryClientProvider client={qc}>
      <TcnScrapeForm />
    </QueryClientProvider>,
  );
  return {
    ...utils,
    rerenderForm: () =>
      utils.rerender(
        <QueryClientProvider client={qc}>
          <TcnScrapeForm />
        </QueryClientProvider>,
      ),
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  // `clearAllMocks` efface les appels enregistrés, pas l'implémentation posée
  // par un `mockResolvedValue` d'un test précédent : sans ce repli, un test qui
  // détourne `detectProvider` fait fuir sa réponse vers les suivants.
  vi.mocked(apiClient.detectProvider).mockResolvedValue({ provider: "klikego", supported: true });
  importMock.set({
    running: false,
    phase: "idle",
    imported: 0,
    updated: 0,
    skipped: 0,
    cached: false,
    courses: [],
    heatsEnumerated: 0,
    heatsImported: 0,
    heatsCached: 0,
    heatsFailed: 0,
    failures: [],
    error: null,
    errorStatus: null,
    retryAfter: null,
    heatIndex: 0,
    heatsScrapingTotal: 0,
    heatLabel: "",
    detailDone: 0,
    detailTotal: 0,
  });
});

describe("TcnScrapeForm — navigation vers les courses importées (#135)", () => {
  it("solo : rend un bouton primary qui file vers /courses/{id}", () => {
    importMock.set({
      phase: "done",
      imported: 12,
      skipped: 0,
      courses: [
        { id: 42, name: "Triathlon de Nantes 2026", event_type: "triathlon-m" },
      ],
    });
    renderForm();
    const link = screen.getByRole("link", {
      name: /Voir les résultats de « Triathlon de Nantes 2026 »/,
    });
    expect(link.getAttribute("href")).toBe("/courses/42");
  });

  it("multi : rend un sélecteur, avec la 1re course pré-sélectionnée", () => {
    importMock.set({
      phase: "done",
      imported: 300,
      skipped: 0,
      courses: [
        { id: 1, name: "Triathlon S", event_type: "triathlon-s" },
        { id: 2, name: "Triathlon M", event_type: "triathlon-m" },
        { id: 3, name: "Triathlon L", event_type: "triathlon-l" },
      ],
    });
    renderForm();
    // Le titre du sélecteur annonce le nombre d'épreuves (compteur unique —
    // le reste du texte est en fragments donc pas testé littéralement).
    // « épreuve », jamais « course », dans un libellé (revue de code #478).
    expect(screen.getByText(/3 épreuves importées/)).toBeInTheDocument();
    // Le bouton file vers la première course par défaut, sans interaction.
    const link = screen.getByRole("link", { name: /Voir les résultats/ });
    expect(link.getAttribute("href")).toBe("/courses/1");
  });

  it("multi : sélectionner une autre course met à jour la cible du bouton", async () => {
    importMock.set({
      phase: "done",
      imported: 300,
      skipped: 0,
      courses: [
        { id: 1, name: "Triathlon S", event_type: "triathlon-s" },
        { id: 2, name: "Triathlon M", event_type: "triathlon-m" },
      ],
    });
    renderForm();
    // Le sélecteur est un `<select>` natif restylé (label accessible via aria-label).
    const select = screen.getByRole("combobox", { name: /Choisir l'épreuve/ });
    await userEvent.selectOptions(select, "2");
    expect(
      screen.getByRole("link", { name: /Voir les résultats/ }).getAttribute("href"),
    ).toBe("/courses/2");
  });

  it("propose aussi la navigation sur le doublon (résultats déjà en base)", () => {
    // Chemin cache TTL frais : imported=0, skipped>0, cached=true.
    importMock.set({
      phase: "done",
      cached: true,
      imported: 0,
      skipped: 250,
      courses: [
        { id: 7, name: "Duathlon de La Baule 2026", event_type: "duathlon-s" },
      ],
    });
    renderForm();
    // L'alerte doublon (title « Résultats déjà enregistrés ») doit exister ET
    // porter le lien : c'est le point de l'issue #135 pour ce cas.
    expect(screen.getByText(/Résultats déjà enregistrés/)).toBeInTheDocument();
    const link = screen.getByRole("link", {
      name: /Voir les résultats de « Duathlon de La Baule 2026 »/,
    });
    expect(link.getAttribute("href")).toBe("/courses/7");
  });

  it("ne rend rien si le backend n'a remonté aucune course (import vide)", () => {
    importMock.set({
      phase: "done",
      imported: 0,
      skipped: 0,
      courses: [],
    });
    renderForm();
    expect(screen.queryByRole("link", { name: /Voir les résultats/ })).not.toBeInTheDocument();
  });
});

describe("TcnScrapeForm — validation de l'URL avant appel backend (#249)", () => {
  it("bouton désactivé et pas d'appel `start` sur entrée non-URL", async () => {
    renderForm();
    const bouton = screen.getByRole("button", { name: /Enregistrer les résultats/ });
    // À vide, le bouton est déjà désactivé (rien à envoyer).
    expect(bouton).toBeDisabled();

    const input = champUrl();
    await userEvent.type(input, "pas une url");
    expect(bouton).toBeDisabled();
    // Message d'erreur affiché en français.
    expect(screen.getByRole("alert")).toHaveTextContent(/URL valide/i);

    // Un clic quand-même ne doit rien envoyer au backend.
    await userEvent.click(bouton);
    expect(importMock.start).not.toHaveBeenCalled();
  });

  it("touche Entrée n'envoie rien sur entrée invalide", async () => {
    renderForm();
    const input = champUrl();
    await userEvent.type(input, "javascript:alert(1){enter}");
    expect(importMock.start).not.toHaveBeenCalled();
    // Champ marqué invalide pour les lecteurs d'écran.
    expect(input).toHaveAttribute("aria-invalid", "true");
  });

  it("URL http(s) valide : bouton actif, pas d'erreur, `start` appelé", async () => {
    renderForm();
    const input = champUrl();
    await userEvent.type(input, "https://www.klikego.com/resultats/x");
    const bouton = screen.getByRole("button", { name: /Enregistrer les résultats/ });
    expect(bouton).not.toBeDisabled();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    await userEvent.click(bouton);
    expect(importMock.start).toHaveBeenCalledWith("https://www.klikego.com/resultats/x", true);
  });
});

describe("TcnScrapeForm — rafraîchissement de la liste après import (#201)", () => {
  it("appelle router.refresh() quand le SSE émet phase=done avec un import réel", () => {
    importMock.set({
      phase: "done",
      cached: false,
      imported: 12,
      skipped: 0,
      courses: [{ id: 42, name: "Triathlon de Nantes 2026", event_type: "triathlon-m" }],
    });
    renderForm();
    expect(refreshMock).toHaveBeenCalledTimes(1);
  });

  it("n'appelle pas router.refresh() sur un doublon (cache TTL frais)", () => {
    importMock.set({
      phase: "done",
      cached: true,
      imported: 0,
      skipped: 250,
      courses: [{ id: 7, name: "Duathlon de La Baule 2026", event_type: "duathlon-s" }],
    });
    renderForm();
    expect(refreshMock).not.toHaveBeenCalled();
  });

  it("n'appelle pas router.refresh() tant que la phase n'est pas `done`", () => {
    importMock.set({
      phase: "scraping",
      imported: 0,
      skipped: 0,
      courses: [],
    });
    renderForm();
    expect(refreshMock).not.toHaveBeenCalled();
  });
});

describe("TcnScrapeForm — un seul verdict avant d'essayer (#492, ACT-6)", () => {
  it("annonce l'adresse non reconnue une seule fois, et nulle part ailleurs", async () => {
    vi.mocked(apiClient.detectProvider).mockResolvedValue({ provider: "", supported: false });
    renderForm();
    await userEvent.type(champUrl(), "https://chronopuce.test/x");

    expect(
      await screen.findByText("Aucun chronométreur ne reconnaît cette adresse."),
    ).toBeInTheDocument();
    // Le badge rouge et l'alerte jaune disaient le même verdict au même
    // moment : trois formulations font douter qu'il s'agisse du même.
    expect(screen.queryByText("Non supporté — saisie manuelle")).not.toBeInTheDocument();
    expect(screen.queryByText("Impossible d'importer automatiquement")).not.toBeInTheDocument();
    expect(importMock.start).not.toHaveBeenCalled();
  });

  it("désactive le bouton principal quand aucun chronométreur ne reconnaît l'adresse", async () => {
    vi.mocked(apiClient.detectProvider).mockResolvedValue({ provider: "", supported: false });
    renderForm();
    await userEvent.type(champUrl(), "https://chronopuce.test/x");

    // Il restait actif et promettait le contraire du verdict affiché juste
    // au-dessus : `disabled` ne testait que `running || !urlIsValid`.
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /Enregistrer les résultats/ })).toBeDisabled(),
    );
  });

  it("rattache le bouton principal au verdict qui le désactive", async () => {
    // Le bouton se désactivait en silence : sans `aria-describedby`, la raison
    // du blocage n'est nulle part pour qui l'atteint au clavier (WCAG 4.1.3).
    vi.mocked(apiClient.detectProvider).mockResolvedValue({ provider: "", supported: false });
    renderForm();
    await userEvent.type(champUrl(), "https://chronopuce.test/x");

    const verdict = await screen.findByRole("status");
    expect(screen.getByRole("button", { name: /Enregistrer les résultats/ })).toHaveAttribute(
      "aria-describedby",
      verdict.id,
    );
  });

  it("n'ouvre pas la saisie manuelle par-dessus un import qui tourne", async () => {
    // L'ancienne alerte anticipée portait un `phase === "idle"` : éditer le
    // champ pendant un import affichait sinon la sortie manuelle à côté de la
    // barre de progression, et ouvrait un formulaire sous un import en cours.
    vi.mocked(apiClient.detectProvider).mockResolvedValue({ provider: "", supported: false });
    importMock.set({ phase: "scraping", running: true });
    renderForm();
    await userEvent.type(champUrl(), "https://chronopuce.test/x");

    await screen.findByRole("status");
    expect(screen.queryByRole("button", { name: "Saisir à la main" })).not.toBeInTheDocument();
  });

  it("la touche Entrée ne contourne pas le bouton désactivé", async () => {
    vi.mocked(apiClient.detectProvider).mockResolvedValue({ provider: "", supported: false });
    renderForm();
    await userEvent.type(champUrl(), "https://chronopuce.test/x");
    await screen.findByText("Aucun chronométreur ne reconnaît cette adresse.");

    await userEvent.type(champUrl(), "{enter}");

    expect(importMock.start).not.toHaveBeenCalled();
  });

  it("laisse le bouton actif quand le chronométreur est reconnu, et le dit", async () => {
    renderForm();
    await userEvent.type(champUrl(), "https://www.klikego.com/resultats/x");

    expect(await screen.findByText("Chronométreur reconnu : Klikego")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Enregistrer les résultats/ })).not.toBeDisabled();
  });

  it("au repos, nomme les chronométreurs pris en charge avant tout collage", async () => {
    renderForm();

    expect(await screen.findByText("Klikego")).toBeInTheDocument();
    expect(screen.getByText("Wiclax")).toBeInTheDocument();
  });

  it("« Saisir à la main » depuis le verdict ouvre le formulaire", async () => {
    vi.mocked(apiClient.detectProvider).mockResolvedValue({ provider: "", supported: false });
    renderForm();
    await userEvent.type(champUrl(), "https://chronopuce.test/x");

    await userEvent.click(await screen.findByRole("button", { name: "Saisir à la main" }));

    expect(
      screen.getByRole("button", { name: "Enregistrer votre participation" }),
    ).toBeInTheDocument();
  });
});

describe("TcnScrapeForm — portée de l'import (#698)", () => {
  it("n'affiche pas le contrôle pour un provider sans fanout", async () => {
    vi.mocked(apiClient.detectProvider).mockResolvedValue({
      provider: "timepulse", supported: true, fanout: false, default_single_heat: true,
    });
    renderForm();
    await userEvent.type(champUrl(), "https://timepulse.fr/x");
    // Le verdict d'abord : `toHaveBeenCalled` ne prouve que l'**appel**, et
    // l'absence était donc constatée avant même que la réponse résolue ait été
    // rendue — un négatif qui serait passé quoi qu'affiche le composant.
    await screen.findByText(/Chronométreur reconnu/);
    expect(screen.queryByRole("group", { name: /Portée de l'import/ })).not.toBeInTheDocument();
  });

  it("nomme le groupe d'options à l'écran, pas seulement aux lecteurs d'écran", async () => {
    // `aria-label` sur un `role="radiogroup"` est invisible aux yeux : les deux
    // options s'affichaient sans que rien ne dise de quoi elles sont les deux
    // faces. `<fieldset>`/`<legend>` nomme le groupe pour tout le monde.
    vi.mocked(apiClient.detectProvider).mockResolvedValue({
      provider: "klikego", supported: true, fanout: true, default_single_heat: true,
    });
    renderForm();
    await userEvent.type(champUrl(), "https://www.klikego.com/resultats/foo/1?heat=x");

    const groupe = await screen.findByRole("group", { name: /Portée de l'import/ });
    expect(within(groupe).getByText("Portée de l'import")).toBeVisible();
  });

  it("affiche le contrôle et pré-coche « import unique » quand le serveur le recommande", async () => {
    vi.mocked(apiClient.detectProvider).mockResolvedValue({
      provider: "wiclax", supported: true, fanout: true, default_single_heat: true,
    });
    renderForm();
    await userEvent.type(champUrl(), "https://wiclax-results.com/x");
    await waitFor(() =>
      expect(screen.getByRole("radio", { name: /uniquement cette page/ })).toBeChecked(),
    );
    expect(screen.getByRole("radio", { name: /tout l.événement/ })).not.toBeChecked();
  });

  it("pré-coche « fanout complet » quand le serveur le recommande (Klikego sans sélecteur)", async () => {
    vi.mocked(apiClient.detectProvider).mockResolvedValue({
      provider: "klikego", supported: true, fanout: true, default_single_heat: false,
    });
    renderForm();
    await userEvent.type(champUrl(), "https://www.klikego.com/resultats/foo/1");
    await waitFor(() =>
      expect(screen.getByRole("radio", { name: /tout l.événement/ })).toBeChecked(),
    );
    await userEvent.click(screen.getByRole("button", { name: /Enregistrer les résultats/ }));
    expect(importMock.start).toHaveBeenCalledWith(
      "https://www.klikego.com/resultats/foo/1", false,
    );
  });

  it("permet de basculer vers le fanout complet, et `start` reçoit `false`", async () => {
    vi.mocked(apiClient.detectProvider).mockResolvedValue({
      provider: "wiclax", supported: true, fanout: true, default_single_heat: true,
    });
    renderForm();
    await userEvent.type(champUrl(), "https://wiclax-results.com/x");
    await waitFor(() =>
      expect(screen.getByRole("radio", { name: /tout l.événement/ })).toBeInTheDocument(),
    );
    await userEvent.click(screen.getByRole("radio", { name: /tout l.événement/ }));
    await userEvent.click(screen.getByRole("button", { name: /Enregistrer les résultats/ }));
    expect(importMock.start).toHaveBeenCalledWith("https://wiclax-results.com/x", false);
  });
});

describe("TcnScrapeForm — le champ URL au doigt (#492, ACT-5)", () => {
  it("déclare le clavier que ce champ attend", async () => {
    renderForm();
    const champ = champUrl();

    // Une URL n'est ni capitalisée, ni corrigée, et la touche d'action du
    // clavier mobile doit lancer l'import plutôt qu'insérer un retour ligne.
    expect(champ).toHaveAttribute("autocapitalize", "none");
    expect(champ).toHaveAttribute("spellcheck", "false");
    expect(champ).toHaveAttribute("enterkeyhint", "go");
    expect(champ).toHaveAttribute("inputmode", "url");
  });

  it("« Coller » remplit le champ depuis le presse-papiers", async () => {
    const readText = vi.fn().mockResolvedValue("https://www.klikego.com/resultats/x");
    Object.assign(navigator, { clipboard: { readText } });
    renderForm();

    await userEvent.click(screen.getByRole("button", { name: "Coller l'adresse" }));

    await waitFor(() =>
      expect(champUrl()).toHaveValue("https://www.klikego.com/resultats/x"),
    );
  });

  it("« Effacer » vide le champ, et n'apparaît que s'il y a quelque chose à effacer", async () => {
    renderForm();
    expect(screen.queryByRole("button", { name: "Effacer l'adresse" })).not.toBeInTheDocument();

    await userEvent.type(champUrl(), "https://www.klikego.com/resultats/x");
    await userEvent.click(screen.getByRole("button", { name: "Effacer l'adresse" }));

    expect(champUrl()).toHaveValue("");
  });
});

describe("TcnScrapeForm — repli sur échec d'import", () => {
  it("signale le fournisseur et bascule en saisie manuelle", async () => {
    const { rerenderForm } = renderForm();
    await userEvent.type(
      champUrl(),
      "http://x.test/ev",
    );
    await userEvent.click(screen.getByRole("button", { name: /Enregistrer les résultats/ }));
    importMock.set({ phase: "error", error: "boom" });
    rerenderForm();

    await waitFor(() =>
      expect(apiClient.reportPendingProvider).toHaveBeenCalledWith("http://x.test/ev"),
    );
    expect(
      screen.getByRole("button", { name: "Enregistrer votre participation" }),
    ).toBeInTheDocument();
  });
});

describe("TcnScrapeForm — trois échecs, trois écrans (#491, ACT-2)", () => {
  it("plafond de débit : annonce l'attente, sans saisie manuelle ni signalement", async () => {
    const { rerenderForm } = renderForm();
    await userEvent.type(
      champUrl(),
      "https://www.klikego.com/resultats/x",
    );
    importMock.set({ phase: "error", error: "Trop de demandes", errorStatus: 429, retryAfter: 180 });
    rerenderForm();

    expect(screen.getByText("Trop d'imports dans l'heure")).toBeInTheDocument();
    expect(screen.getByText(/Réessayez dans 3 minutes/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Saisir à la main" })).not.toBeInTheDocument();
    await waitFor(() => expect(apiClient.detectProvider).toHaveBeenCalled());
    expect(apiClient.reportPendingProvider).not.toHaveBeenCalled();
  });

  it("service muet : propose de réessayer, sans signaler le fournisseur", async () => {
    const { rerenderForm } = renderForm();
    await userEvent.type(
      champUrl(),
      "https://www.klikego.com/resultats/x",
    );
    importMock.set({ phase: "error", error: "Boum", errorStatus: 500 });
    rerenderForm();

    expect(screen.getByText("Le service n'a pas répondu")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Saisir à la main" })).not.toBeInTheDocument();
    expect(apiClient.reportPendingProvider).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: "Réessayer" }));
    expect(importMock.start).toHaveBeenCalledWith("https://www.klikego.com/resultats/x", true);
  });

  it("coupure réseau : même écran que le service muet", async () => {
    const { rerenderForm } = renderForm();
    await userEvent.type(
      champUrl(),
      "https://www.klikego.com/resultats/x",
    );
    importMock.set({ phase: "error", error: "Failed to fetch", errorStatus: 0 });
    rerenderForm();

    expect(screen.getByText("Le service n'a pas répondu")).toBeInTheDocument();
    expect(apiClient.reportPendingProvider).not.toHaveBeenCalled();
  });
});

describe("TcnScrapeForm — le bilan dit toute la vérité (#491, ACT-3)", () => {
  it("rend les cinq chiffres, mises à jour comprises", () => {
    importMock.set({
      phase: "done",
      imported: 12,
      updated: 5,
      skipped: 3,
      courses: [{ id: 42, name: "Triathlon de Nantes 2026", event_type: "triathlon-m" }],
    });
    renderForm();

    expect(screen.getByText(/12 résultats ajoutés/)).toBeInTheDocument();
    expect(screen.getByText(/5 mis à jour/)).toBeInTheDocument();
    expect(screen.getByText(/3 déjà présents/)).toBeInTheDocument();
  });

  it("un import qui n'a fait que mettre à jour ne s'annonce pas comme vide", () => {
    importMock.set({ phase: "done", imported: 0, updated: 40, skipped: 0, courses: [] });
    renderForm();

    expect(screen.getByText(/40 mis à jour/)).toBeInTheDocument();
    expect(screen.queryByText("Résultats déjà enregistrés")).not.toBeInTheDocument();
  });

  it("séries en échec : statut dégradé, chiffres des séries et cause de chaque échec", () => {
    importMock.set({
      phase: "done",
      imported: 120,
      updated: 0,
      skipped: 0,
      heatsEnumerated: 12,
      heatsImported: 9,
      heatsCached: 0,
      heatsFailed: 3,
      // Ce que le backend met réellement dans `reason` : `str(exc)`, anglais
      // et technique (`import_service`/`klikego.py`). L'écran ne doit pas le
      // rendre verbatim (Principe I).
      failures: [
        { heat_slug: "relais-h", reason: "Server error '502 Bad Gateway' for url 'https://x'" },
        { heat_slug: "jeunes", reason: "ReadTimeout: timed out" },
        { heat_slug: "decouverte", reason: "list index out of range" },
      ],
      courses: [{ id: 42, name: "Triathlon de Nantes 2026", event_type: "triathlon-m" }],
    });
    renderForm();

    expect(screen.getByText("Import partiel : 3 séries sur 12 manquent")).toBeInTheDocument();
    expect(screen.getByText(/Série « relais-h » : le chronométreur était indisponible/)).toBeInTheDocument();
    expect(screen.getByText(/Série « jeunes » : le chronométreur n'a pas répondu à temps/)).toBeInTheDocument();
    expect(screen.getByText(/Série « decouverte » : la page n'a pas pu être lue/)).toBeInTheDocument();
    expect(screen.queryByText(/Bad Gateway/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Relancer l'import" })).toBeInTheDocument();
  });

  it("aucune série en échec : le succès reste un succès", () => {
    importMock.set({
      phase: "done",
      imported: 120,
      heatsEnumerated: 12,
      heatsImported: 12,
      heatsFailed: 0,
      failures: [],
      courses: [{ id: 42, name: "Triathlon de Nantes 2026", event_type: "triathlon-m" }],
    });
    renderForm();

    expect(screen.getByText("Résultats enregistrés avec succès !")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Relancer l'import" })).not.toBeInTheDocument();
  });
});

describe("TcnScrapeForm — une attente habitée (#491, ACT-4)", () => {
  it("compte le temps écoulé pendant le scraping", () => {
    vi.useFakeTimers();
    try {
      importMock.set({ phase: "scraping", running: true, message: "Récupération des participants…" });
      renderForm();

      act(() => {
        vi.advanceTimersByTime(65_000);
      });

      expect(screen.getByText(/1 min 5 s/)).toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });

  it("« Annuler l'import » coupe le flux", async () => {
    importMock.set({ phase: "scraping", running: true, message: "Récupération des participants…" });
    renderForm();

    await userEvent.click(screen.getByRole("button", { name: "Annuler l'import" }));

    expect(importMock.cancel).toHaveBeenCalled();
  });

  it("prévient avant de quitter l'onglet tant que l'import tourne", () => {
    importMock.set({ phase: "scraping", running: true });
    const { unmount } = renderForm();

    const evenement = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(evenement);
    expect(evenement.defaultPrevented).toBe(true);

    unmount();
    const apres = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(apres);
    expect(apres.defaultPrevented).toBe(false);
  });

  it("ne prévient pas quand aucun import ne tourne", () => {
    renderForm();
    const evenement = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(evenement);
    expect(evenement.defaultPrevented).toBe(false);
  });
});

describe("TcnScrapeForm — suites des revues (#491)", () => {
  it("le décompte du plafond décompte vraiment", () => {
    vi.useFakeTimers();
    try {
      importMock.set({ phase: "error", error: "Trop de demandes", errorStatus: 429, retryAfter: 180 });
      renderForm();
      expect(screen.getByText(/Réessayez dans 3 minutes/)).toBeInTheDocument();

      act(() => {
        vi.advanceTimersByTime(130_000);
      });

      expect(screen.getByText(/moins d'une minute/)).toBeInTheDocument();

      act(() => {
        vi.advanceTimersByTime(60_000);
      });

      expect(screen.getByText(/Vous pouvez réessayer maintenant/)).toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });

  it("corriger l'adresse après un échec ne re-signale pas le fournisseur à chaque frappe", async () => {
    const { rerenderForm } = renderForm();
    const champ = champUrl();
    await userEvent.type(champ, "http://x.test/ev");
    await userEvent.click(screen.getByRole("button", { name: /Enregistrer les résultats/ }));
    importMock.set({ phase: "error", error: "boom", errorStatus: null });
    rerenderForm();
    await waitFor(() => expect(apiClient.reportPendingProvider).toHaveBeenCalledTimes(1));

    await userEvent.type(champ, "ent");

    expect(apiClient.reportPendingProvider).toHaveBeenCalledTimes(1);
    expect(apiClient.reportPendingProvider).toHaveBeenCalledWith("http://x.test/ev");
  });

  it("séries en échec servies par le cache : le doublon ne masque plus les manques", () => {
    importMock.set({
      phase: "done",
      cached: true,
      imported: 0,
      updated: 0,
      skipped: 250,
      heatsEnumerated: 12,
      heatsImported: 0,
      heatsCached: 11,
      heatsFailed: 1,
      failures: [{ heat_slug: "relais-h", reason: "ReadTimeout" }],
      courses: [{ id: 7, name: "Duathlon de La Baule 2026", event_type: "duathlon-s" }],
    });
    renderForm();

    expect(screen.getByText("Import partiel : 1 série sur 12 manque")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Relancer l'import" })).toBeInTheDocument();
    expect(screen.queryByText("Résultats déjà enregistrés")).not.toBeInTheDocument();
  });

  it("borne la liste des séries perdues au-delà de cinq", () => {
    importMock.set({
      phase: "done",
      imported: 10,
      heatsEnumerated: 12,
      heatsFailed: 7,
      failures: Array.from({ length: 7 }, (_, i) => ({
        heat_slug: `serie-${i}`,
        reason: "ReadTimeout",
      })),
      courses: [],
    });
    renderForm();

    expect(screen.getByText(/et 2 autres séries/)).toBeInTheDocument();
  });

  it("annuler dit ce que l'annulation laisse derrière elle", async () => {
    importMock.set({ phase: "scraping", running: true });
    renderForm();

    await userEvent.click(screen.getByRole("button", { name: "Annuler l'import" }));

    expect(importMock.cancel).toHaveBeenCalled();
    expect(toast.message).toHaveBeenCalledWith(
      "Import interrompu",
      expect.objectContaining({
        description: expect.stringContaining("déjà enregistrés sont conservés"),
      }),
    );
  });
});

describe("TcnScrapeForm — accusé de réception de la saisie manuelle (ACT-1)", () => {
  async function ouvrirSaisieManuelle() {
    vi.mocked(apiClient.detectProvider).mockResolvedValue({ provider: "", supported: false });
    renderForm();
    await userEvent.type(
      champUrl(),
      "https://chronopuce.test/x",
    );
    await userEvent.click(await screen.findByRole("button", { name: "Saisir à la main" }));
  }

  async function saisirEtEnregistrer() {
    await userEvent.type(screen.getByLabelText("Prénom"), "Jean");
    await userEvent.type(screen.getByLabelText("Nom"), "DUPONT");
    fireEvent.change(screen.getByLabelText("Date"), { target: { value: "2026-05-16" } });
    await userEvent.type(screen.getByLabelText("Nom de l'épreuve"), "Triathlon de Nantes");
    await userEvent.selectOptions(screen.getByLabelText("Discipline"), "triathlon");
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer votre participation" }));
  }

  function participationCreee() {
    vi.mocked(apiClient.saveParticipation).mockResolvedValue({
      id: 77,
      course: { id: 42, name: "Triathlon de Nantes", event_type: "triathlon-m" },
    } as never);
  }

  it("l'accroche annonce la validation par un bénévole au lieu de la nier", async () => {
    await ouvrirSaisieManuelle();
    expect(
      screen.getByText(/vérifiée par un bénévole du club avant d'apparaître/i),
    ).toBeInTheDocument();
  });

  it("après enregistrement, une alerte persistante dit la mise en attente et mène au résultat", async () => {
    participationCreee();
    await ouvrirSaisieManuelle();
    await saisirEtEnregistrer();

    expect(
      await screen.findByText(/en attente de validation par un bénévole du club/i),
    ).toBeInTheDocument();
    expect(screen.getByText("En attente de validation")).toBeInTheDocument();
    expect(screen.getByText(/sous quelques jours/i)).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /Voir ma participation/i }).getAttribute("href"),
    ).toBe("/courses/42/participations/77");
    // Le formulaire se referme : l'accusé de réception le remplace, et
    // l'invitation à saisir à la main ne contredit plus le succès affiché.
    expect(
      screen.queryByRole("button", { name: "Enregistrer votre participation" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Saisir à la main" })).not.toBeInTheDocument();
  });

  it("annonce l'accusé de réception aux lecteurs d'écran", async () => {
    participationCreee();
    await ouvrirSaisieManuelle();
    await saisirEtEnregistrer();

    // Le formulaire est démonté au moment où la carte apparaît : sans région
    // live, plus rien n'est annoncé ni focalisé (WCAG 4.1.3, #477). L'écran en
    // porte deux depuis #492 — le verdict du fournisseur reste sous le champ,
    // qui n'a pas été vidé.
    const annonce = (await screen.findAllByRole("status")).find(
      (n) => n.id !== "scrape-provider-verdict",
    );
    expect(annonce).toHaveTextContent(/en attente de validation par un bénévole/i);
  });

  it("offre une sortie pour saisir une seconde participation", async () => {
    participationCreee();
    await ouvrirSaisieManuelle();
    await saisirEtEnregistrer();

    await userEvent.click(
      await screen.findByRole("button", { name: "Saisir une autre participation" }),
    );

    expect(
      screen.getByRole("button", { name: "Enregistrer votre participation" }),
    ).toBeInTheDocument();
  });

  it("coller une nouvelle adresse non reconnue rouvre l'invitation à la saisie manuelle", async () => {
    participationCreee();
    await ouvrirSaisieManuelle();
    await saisirEtEnregistrer();
    await screen.findByText(/en attente de validation par un bénévole du club/i);

    await userEvent.type(champUrl(), "/autre");

    expect(
      await screen.findByRole("button", { name: "Saisir à la main" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/en attente de validation par un bénévole du club/i),
    ).not.toBeInTheDocument();
  });

  it("un échec d'enregistrement laisse le formulaire ouvert et affiche une alerte persistante", async () => {
    vi.mocked(apiClient.saveParticipation).mockRejectedValue(new Error("Service indisponible"));
    await ouvrirSaisieManuelle();
    await saisirEtEnregistrer();

    expect(
      await screen.findByText("Impossible d'enregistrer votre participation"),
    ).toBeInTheDocument();
    expect(screen.getByText(/Service indisponible/)).toBeInTheDocument();
    // Ce qui a été saisi reste sous les yeux, prêt à être renvoyé.
    expect(
      screen.getByRole("button", { name: "Enregistrer votre participation" }),
    ).toBeInTheDocument();
  });
});

describe("TcnScrapeForm — progression phase C Klikego (#583)", () => {
  it("affiche l'avancement des participants au sein de la série en cours", () => {
    importMock.set({
      phase: "scraping",
      heatIndex: 1,
      heatsScrapingTotal: 3,
      heatLabel: "Triathlon S",
      detailDone: 20,
      detailTotal: 50,
    });
    renderForm();

    expect(screen.getByText("20/50 participants")).toBeInTheDocument();
  });

  it("n'affiche rien tant que la phase C n'a pas rapporté sa première tranche", () => {
    importMock.set({
      phase: "scraping",
      heatIndex: 1,
      heatsScrapingTotal: 3,
      heatLabel: "Triathlon S",
      detailDone: 0,
      detailTotal: 0,
    });
    renderForm();

    expect(screen.queryByText(/participants$/)).not.toBeInTheDocument();
  });
});
