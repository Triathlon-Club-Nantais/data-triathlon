import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { ApiError } from "@/lib/api/client";
import type { AuthMethod } from "@/lib/types";

const { listAuthMethods } = vi.hoisted(() => ({ listAuthMethods: vi.fn() }));
const { parametres } = vi.hoisted(() => ({ parametres: new URLSearchParams() }));
const { capture } = vi.hoisted(() => ({ capture: vi.fn() }));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { ...original.apiClient, listAuthMethods } };
});

vi.mock("next/navigation", () => ({
  useSearchParams: () => parametres,
}));

vi.mock("posthog-js", () => ({ default: { capture, init: vi.fn(), get_explicit_consent_status: vi.fn() } }));

const { preload } = vi.hoisted(() => ({ preload: vi.fn() }));
vi.mock("@/lib/posthog", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/posthog")>();
  return {
    ...original,
    withPostHog: (call: Parameters<typeof original.withPostHog>[0]) => {
      preload();
      original.withPostHog(call);
    },
  };
});

import LoginPage from "./page";

function afficher(methodes: AuthMethod[], erreur?: string) {
  listAuthMethods.mockResolvedValue(methodes);
  parametres.delete("error");
  if (erreur) parametres.set("error", erreur);

  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <LoginPage />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  capture.mockClear();
  // captureEvent (lib/posthog.ts) ne délègue à posthog-js que si le token est
  // présent — sans ce stub, l'assertion sur `capture` ne verrait jamais rien.
  vi.stubEnv("NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN", "test-token");
  vi.stubEnv("NEXT_PUBLIC_POSTHOG_HOST", "https://eu.posthog.com");
});

describe("Page de connexion — méthodes", () => {
  it("rend un bouton par méthode déclarée par l'API", async () => {
    afficher([
      { slug: "github", label: "GitHub", audience: "admin" },
      { slug: "ailleurs", label: "Ailleurs", audience: "member" },
    ]);

    await waitFor(() => expect(screen.getByRole("link", { name: /GitHub/ })).toBeInTheDocument());
    expect(screen.getByRole("link", { name: /Ailleurs/ })).toBeInTheDocument();
  });

  // #1031 : sans le code d'accès, rien ne se consulte ; la phrase le dit.
  // #1666 : la connexion adhérent ouvre l'espace personnel ; sans compte, le code d'accès suffit.
  it("présente l'espace personnel et le code d'accès du club, pas un site consultable sans rien", async () => {
    afficher([]);

    expect(
      screen.getByText(
        "La connexion adhérent ouvre votre espace personnel : vos résultats, vos objectifs et votre page d'athlète. Les résultats du club se consultent aussi sans compte, avec le code d'accès du club.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText(/entièrement consultable/)).not.toBeInTheDocument();
  });

  it("pointe chaque bouton vers l'entrée de parcours du backend", async () => {
    afficher([{ slug: "github", label: "GitHub", audience: "admin" }]);

    const lien = await screen.findByRole("link", { name: /GitHub/ });
    expect(lien).toHaveAttribute("href", "/api/v1/auth/github/authorize");
  });

  it("charge posthog-js dès l'affichage, pour que login_initiated parte avant la navigation (#1394)", () => {
    preload.mockClear();
    afficher([{ slug: "github", label: "GitHub", audience: "admin" }]);

    expect(preload).toHaveBeenCalled();
  });

  it("capture login_initiated via sendBeacon avant que la navigation ne parte (#339)", async () => {
    // capture() doit survivre au unload : send_instantly + sendBeacon, pas la
    // file batchée par défaut qu'une navigation immédiate peut couper court.
    afficher([{ slug: "github", label: "GitHub", audience: "admin" }]);

    const lien = await screen.findByRole("link", { name: /GitHub/ });
    await userEvent.click(lien);

    await waitFor(() =>
      expect(capture).toHaveBeenCalledWith(
        "login_initiated",
        { provider: "github" },
        { transport: "sendBeacon", send_instantly: true },
      ),
    );
  });

  it("ne code en dur aucune méthode : liste vide, aucun bouton", async () => {
    afficher([]);

    await waitFor(() =>
      expect(screen.getByText(/aucun moyen de connexion/i)).toBeInTheDocument(),
    );
    expect(screen.queryByRole("link", { name: /GitHub/ })).not.toBeInTheDocument();
  });
});

const ENTRA: AuthMethod = { slug: "entra", label: "Google ou code par e-mail", audience: "member" };
const GITHUB: AuthMethod = { slug: "github", label: "GitHub", audience: "admin" };
const INDISPONIBLE =
  "La connexion adhérent n'est pas encore disponible sur ce site. Les résultats du club se consultent avec le code d'accès.";

function region(nom: string) {
  return screen.getByRole("region", { name: nom });
}

describe("Page de connexion — deux parcours (#1666)", () => {
  it("sépare l'espace adhérent de l'administration, l'adhérent en premier", async () => {
    afficher([GITHUB, ENTRA]);

    const adherent = await screen.findByRole("link", {
      name: "Continuer avec Google ou code par e-mail",
    });
    const admin = screen.getByRole("link", { name: "Continuer avec GitHub" });
    expect(region("Espace adhérent")).toContainElement(adherent);
    expect(region("Administration")).toContainElement(admin);
    expect(
      within(region("Administration")).getByText("Réservé aux administrateurs du site."),
    ).toBeInTheDocument();
    expect(adherent.compareDocumentPosition(admin) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("sans méthode adhérent, ne rend que le bloc administration", async () => {
    afficher([GITHUB]);

    await screen.findByRole("link", { name: "Continuer avec GitHub" });
    expect(screen.queryByRole("region", { name: "Espace adhérent" })).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Administration" })).toBeInTheDocument();
    expect(screen.getByText(INDISPONIBLE)).toBeInTheDocument();
  });

  it("sans méthode admin, ne rend pas le bloc administration", async () => {
    afficher([ENTRA]);

    await screen.findByRole("link", { name: "Continuer avec Google ou code par e-mail" });
    expect(screen.queryByRole("heading", { name: "Administration" })).not.toBeInTheDocument();
    expect(screen.queryByText(INDISPONIBLE)).not.toBeInTheDocument();
  });

  it.each([
    ["Continuer avec Google ou code par e-mail", "entra"],
    ["Continuer avec GitHub", "github"],
  ])("capture login_initiated au clic sur « %s »", async (nom, provider) => {
    afficher([ENTRA, GITHUB]);

    await userEvent.click(await screen.findByRole("link", { name: nom }));

    await waitFor(() =>
      expect(capture).toHaveBeenCalledWith(
        "login_initiated",
        { provider },
        { transport: "sendBeacon", send_instantly: true },
      ),
    );
  });
});

describe("Page de connexion — refus (US3)", () => {
  it.each([
    ["state_mismatch", /expiré|vérifi/i],
    ["email_unverified", /adresse e-mail vérifiée/i],
    ["account_not_allowed", /compte a été désactivé/i],
    ["provider_error", /refusée ou interrompue/i],
    ["provider_unavailable", /injoignable/i],
  ])("affiche un message français pour %s", async (code, attendu) => {
    afficher([{ slug: "github", label: "GitHub", audience: "admin" }], code);

    expect(await screen.findByText(attendu)).toBeInTheDocument();
  });

  it("retombe sur un message générique pour un code inconnu", async () => {
    afficher([{ slug: "github", label: "GitHub", audience: "admin" }], "code_invente");

    expect(await screen.findByText(/La connexion a échoué/)).toBeInTheDocument();
  });

  it("ne rend jamais un code verbatim", async () => {
    // Le backend n'émet que des codes fermés, mais la page ne doit pas devenir
    // un point d'injection si cette garantie tombait un jour.
    afficher([{ slug: "github", label: "GitHub", audience: "admin" }], "<script>alert(1)</script>");

    expect(await screen.findByText(/La connexion a échoué/)).toBeInTheDocument();
    expect(screen.queryByText(/script/i)).not.toBeInTheDocument();
  });

  it("n'affiche aucun message d'erreur sans paramètre", async () => {
    afficher([{ slug: "github", label: "GitHub", audience: "admin" }]);

    await screen.findByRole("link", { name: /GitHub/ });
    expect(screen.queryByText(/La connexion a échoué/)).not.toBeInTheDocument();
  });
});

describe("Page de connexion — panne du chargement des méthodes (ACT-9a)", () => {
  it("affiche une alerte et un bouton Réessayer, sans coder le message en dur", async () => {
    listAuthMethods.mockRejectedValue(new ApiError(500, "boum"));
    parametres.delete("error");
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <LoginPage />
      </QueryClientProvider>,
    );

    expect(await screen.findByText(/n'ont pas pu être chargés/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Réessayer" })).toBeInTheDocument();
    expect(screen.queryByText(/aucun moyen de connexion/i)).not.toBeInTheDocument();
  });

  it("relance le chargement des méthodes au clic sur Réessayer", async () => {
    listAuthMethods.mockRejectedValueOnce(new ApiError(500, "boum"));
    listAuthMethods.mockResolvedValueOnce([{ slug: "github", label: "GitHub", audience: "admin" }]);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <LoginPage />
      </QueryClientProvider>,
    );

    await userEvent.click(await screen.findByRole("button", { name: "Réessayer" }));

    expect(await screen.findByRole("link", { name: /GitHub/ })).toBeInTheDocument();
  });
});
