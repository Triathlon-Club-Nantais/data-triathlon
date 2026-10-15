import { describe, it, expect, vi, beforeAll } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// Own file on purpose: vitest isolates the module registry per file, so the witness
// below cannot be pre-loaded by another case opening manual entry first.
vi.mock("@/hooks/useImportStream", () => ({
  useImportStream: () => ({
    state: { running: false, phase: "idle", failures: [], courses: [], error: null, errorStatus: null },
    url: "",
    start: vi.fn(),
    cancel: vi.fn(),
    reset: vi.fn(),
    attach: () => () => {},
  }),
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: vi.fn(), push: vi.fn() }) }));
vi.mock("@/lib/api/client", () => ({
  apiClient: {
    detectProvider: vi.fn().mockResolvedValue({ provider: "", supported: false }),
    listProviders: vi.fn().mockResolvedValue(["klikego"]),
    reportPendingProvider: vi.fn().mockResolvedValue({}),
    saveParticipation: vi.fn().mockResolvedValue({}),
  },
}));
vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn(), message: vi.fn() } }));

// Witness of the lazy load (#1395): the manual form, and zod with it, must only be
// imported once manual entry opens.
const manualFormLoaded = vi.hoisted(() => vi.fn());
vi.mock("./ManualResultForm", async (importOriginal) => {
  manualFormLoaded();
  return importOriginal();
});

import { TcnScrapeForm } from "./TcnScrapeForm";

// Warms the form's module graph outside the case timeout (#1389). importActual skips the
// mock factory, so the witness still only counts the component's own import.
beforeAll(async () => {
  await vi.importActual("./ManualResultForm");
}, 30_000);

describe("TcnScrapeForm, lazy manual form (#1395)", () => {
  it("loads the manual form only when manual entry opens", async () => {
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <TcnScrapeForm />
      </QueryClientProvider>,
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: /Adresse des résultats/ }),
      "https://chronopuce.test/x",
    );
    const open = await screen.findByRole("button", { name: "Saisir à la main" });
    expect(manualFormLoaded).not.toHaveBeenCalled();

    await userEvent.click(open);

    expect(
      await screen.findByRole("button", { name: "Enregistrer votre participation" }),
    ).toBeInTheDocument();
    expect(manualFormLoaded).toHaveBeenCalledTimes(1);
  });
});
