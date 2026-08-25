import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
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

vi.mock("posthog-js", () => ({ default: { capture } }));

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
});

describe("Page de connexion — méthodes", () => {
  it("rend un bouton par méthode déclarée par l'API", async () => {
    afficher([
      { slug: "github", label: "GitHub" },
      { slug: "ailleurs", label: "Ailleurs" },
    ]);

    await waitFor(() => expect(screen.getByRole("link", { name: /GitHub/ })).toBeInTheDocument());
    expect(screen.getByRole("link", { name: /Ailleurs/ })).toBeInTheDocument();
  });

  it("pointe chaque bouton vers l'entrée de parcours du backend", async () => {
    afficher([{ slug: "github", label: "GitHub" }]);

    const lien = await screen.findByRole("link", { name: /GitHub/ });
    expect(lien).toHaveAttribute("href", "/api/v1/auth/github/authorize");
  });

  it("capture login_initiated via sendBeacon avant que la navigation ne parte (#339)", async () => {
    // capture() doit survivre au unload : send_instantly + sendBeacon, pas la
    // file batchée par défaut qu'une navigation immédiate peut couper court.
    afficher([{ slug: "github", label: "GitHub" }]);

    const lien = await screen.findByRole("link", { name: /GitHub/ });
    await userEvent.click(lien);

    expect(capture).toHaveBeenCalledWith(
      "login_initiated",
      { provider: "github" },
      { transport: "sendBeacon", send_instantly: true },
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

describe("Page de connexion — refus (US3)", () => {
  it.each([
    ["state_mismatch", /expiré|vérifi/i],
    ["email_unverified", /adresse e-mail vérifiée/i],
    ["account_not_allowed", /n'est pas autorisée/i],
    ["provider_error", /refusée ou interrompue/i],
    ["provider_unavailable", /injoignable/i],
  ])("affiche un message français pour %s", async (code, attendu) => {
    afficher([{ slug: "github", label: "GitHub" }], code);

    expect(await screen.findByText(attendu)).toBeInTheDocument();
  });

  it("retombe sur un message générique pour un code inconnu", async () => {
    afficher([{ slug: "github", label: "GitHub" }], "code_invente");

    expect(await screen.findByText(/La connexion a échoué/)).toBeInTheDocument();
  });

  it("ne rend jamais un code verbatim", async () => {
    // Le backend n'émet que des codes fermés, mais la page ne doit pas devenir
    // un point d'injection si cette garantie tombait un jour.
    afficher([{ slug: "github", label: "GitHub" }], "<script>alert(1)</script>");

    expect(await screen.findByText(/La connexion a échoué/)).toBeInTheDocument();
    expect(screen.queryByText(/script/i)).not.toBeInTheDocument();
  });

  it("n'affiche aucun message d'erreur sans paramètre", async () => {
    afficher([{ slug: "github", label: "GitHub" }]);

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
    listAuthMethods.mockResolvedValueOnce([{ slug: "github", label: "GitHub" }]);
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
