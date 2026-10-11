import { QueryClient, QueryClientProvider, focusManager } from "@tanstack/react-query";
import { render, waitFor } from "@testing-library/react";
import type { ReactElement } from "react";
import { expect, onTestFinished } from "vitest";

/**
 * Rend `ui` jusqu'à ce qu'une requête en échec soit suspendue (#1294) : onglet
 * sans focus, React Query met la relance en pause, et la requête n'a alors ni
 * `data` ni `error`, `isLoading` à faux. Au test de faire échouer l'appel visé.
 */
export async function rendreAvecRelanceSuspendue(ui: ReactElement) {
  focusManager.setFocused(false);
  onTestFinished(() => focusManager.setFocused(undefined));
  const client = new QueryClient({ defaultOptions: { queries: { retry: 1, retryDelay: 0 } } });
  const rendu = render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
  await waitFor(() =>
    expect(client.getQueryCache().getAll().some((query) => query.state.fetchStatus === "paused")).toBe(
      true,
    ),
  );
  return rendu;
}
