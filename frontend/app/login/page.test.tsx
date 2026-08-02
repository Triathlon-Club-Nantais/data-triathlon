import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { AuthMethod } from "@/lib/types";

const { listAuthMethods } = vi.hoisted(() => ({ listAuthMethods: vi.fn() }));
const { parametres } = vi.hoisted(() => ({ parametres: new URLSearchParams() }));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { ...original.apiClient, listAuthMethods } };
});

vi.mock("next/navigation", () => ({
  useSearchParams: () => parametres,
}));

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
