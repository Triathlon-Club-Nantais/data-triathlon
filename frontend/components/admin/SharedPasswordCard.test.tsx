import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";

const api = vi.hoisted(() => ({
  getSiteAccessConfig: vi.fn(),
  replaceSiteAccessPassword: vi.fn(),
  generateSiteAccessPassword: vi.fn(),
  getBenevoleAccessConfig: vi.fn(),
  replaceBenevoleAccessPassword: vi.fn(),
  generateBenevoleAccessPassword: vi.fn(),
}));

vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: api };
});

import { SharedPasswordCard, type SharedPasswordCopy } from "./SharedPasswordCard";

const COPY: SharedPasswordCopy = {
  title: "Carte témoin",
  description: "Description témoin.",
  label: "Champ témoin",
  placeholder: "Saisie témoin",
  generateLabel: "Générer témoin",
  generatedWarning: "Avertissement témoin.",
  replacedToast: "Remplacé témoin.",
  generatedToast: "Généré témoin.",
  dialogTitle: "Dialogue témoin ?",
  dialogDescription: "Corps témoin.",
};

function afficher(props: Partial<React.ComponentProps<typeof SharedPasswordCard>> = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <SharedPasswordCard
        kind="benevole"
        inputId="temoin-password"
        minLength={8}
        refus={{ sujet: "témoin", action: "gérer le témoin" }}
        copy={COPY}
        {...props}
      />
    </QueryClientProvider>,
  );
}

const NON_CONFIGURE = { configured: false, updated_at: null, updated_by: null };

describe("SharedPasswordCard", () => {
  beforeEach(() => {
    Object.values(api).forEach((fn) => fn.mockReset());
  });

  it("renders the copy and minimum length it is given", async () => {
    api.getBenevoleAccessConfig.mockResolvedValue(NON_CONFIGURE);
    afficher();

    expect(await screen.findByText(/non configuré/i)).toBeInTheDocument();
    expect(screen.getByText("Carte témoin")).toBeInTheDocument();
    expect(screen.getByText("Description témoin.")).toBeInTheDocument();
    const champ = screen.getByLabelText("Champ témoin");
    expect(champ).toHaveAttribute("id", "temoin-password");
    expect(champ).toHaveAttribute("minLength", "8");
    expect(champ).toHaveAttribute("placeholder", "Saisie témoin");
    expect(champ).not.toHaveAttribute("aria-describedby");
    expect(screen.getByRole("button", { name: "Générer témoin" })).toBeInTheDocument();
  });

  it("describes the field with the help when one is given", async () => {
    api.getBenevoleAccessConfig.mockResolvedValue(NON_CONFIGURE);
    afficher({ help: "Aide témoin." });
    await screen.findByText(/non configuré/i);

    const champ = screen.getByLabelText("Champ témoin");
    expect(champ).toHaveAttribute("aria-describedby", "temoin-password-aide");
    expect(champ).toHaveAccessibleDescription("Aide témoin.");
  });

  it("routes each kind to its own endpoints", async () => {
    api.getSiteAccessConfig.mockResolvedValue(NON_CONFIGURE);
    api.replaceSiteAccessPassword.mockResolvedValue(NON_CONFIGURE);
    afficher({ kind: "site" });
    await screen.findByText(/non configuré/i);

    await userEvent.type(screen.getByLabelText("Champ témoin"), "un-secret");
    await userEvent.click(screen.getByRole("button", { name: /^remplacer$/i }));
    const dialogue = await screen.findByRole("dialog");
    expect(within(dialogue).getByText("Dialogue témoin ?")).toBeInTheDocument();
    await userEvent.click(within(dialogue).getByRole("button", { name: /^remplacer$/i }));

    await waitFor(() => expect(api.replaceSiteAccessPassword).toHaveBeenCalledWith("un-secret"));
    expect(api.getBenevoleAccessConfig).not.toHaveBeenCalled();
    expect(api.replaceBenevoleAccessPassword).not.toHaveBeenCalled();
  });
});
