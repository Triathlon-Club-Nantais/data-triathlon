import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act } from "react";
import { hydrateRoot } from "react-dom/client";
import { renderToString } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { queryKeys } from "./keys";
import { useHydratedSession } from "./auth";

function BoutonReserve() {
  const session = useHydratedSession();
  const peut = session.data?.permissions.includes("athletes:write") ?? false;
  return <div>{peut ? <button type="button">Corriger la fiche</button> : null}</div>;
}

function arbre(client: QueryClient) {
  return (
    <QueryClientProvider client={client}>
      <BoutonReserve />
    </QueryClientProvider>
  );
}

function clientAvecSession() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
  client.setQueryData(queryKeys.session(), {
    id: 1,
    email: "admin@exemple.fr",
    display_name: "Admin",
    created_at: "2026-01-01T00:00:00Z",
    permissions: ["athletes:write"],
    roles: [],
    groups: [],
  });
  return client;
}

describe("useHydratedSession (#1090)", () => {
  it("hydrate sans écart quand la session est déjà en cache, puis la rend", async () => {
    // Le serveur n'a jamais la session : son HTML ne porte pas le bouton réservé.
    const html = renderToString(arbre(new QueryClient()));
    expect(html).not.toContain("Corriger la fiche");

    const conteneur = document.createElement("div");
    conteneur.innerHTML = html;
    document.body.appendChild(conteneur);
    const ecartHydratation = vi.fn();

    await act(async () => {
      hydrateRoot(conteneur, arbre(clientAvecSession()), { onRecoverableError: ecartHydratation });
    });

    expect(ecartHydratation).not.toHaveBeenCalled();
    expect(conteneur.textContent).toContain("Corriger la fiche");
  });
});
