import { act, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiError } from "@/lib/api/client";

const { siteAccessLogin, push, refresh } = vi.hoisted(() => ({
  siteAccessLogin: vi.fn(),
  push: vi.fn(),
  refresh: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { siteAccessLogin } };
});

vi.mock("next/navigation", () => ({ useRouter: () => ({ push, refresh }) }));

import { SiteAccessGate } from "./SiteAccessGate";

async function seConnecter(motDePasse: string) {
  await userEvent.type(screen.getByLabelText(/mot de passe/i), motDePasse);
  await userEvent.click(screen.getByRole("button", { name: /se connecter/i }));
}

describe("SiteAccessGate", () => {
  beforeEach(() => {
    siteAccessLogin.mockReset();
    push.mockReset();
    refresh.mockReset();
  });

  it("rejoue la page demandée après une connexion réussie", async () => {
    // Défaut, celui du rendu **sur place** par `app/(public_restricted)/layout.tsx` :
    // l'URL est déjà la bonne, il n'y a qu'à rejouer le layout avec le cookie.
    // C'est ce qui préserve la destination d'un lien partagé (revue de #513) —
    // avant, tout finissait sur le tableau de bord.
    siteAccessLogin.mockResolvedValue(null);
    render(<SiteAccessGate />);

    await seConnecter("secret-du-club");

    expect(siteAccessLogin).toHaveBeenCalledWith("secret-du-club");
    expect(refresh).toHaveBeenCalled();
    expect(push).not.toHaveBeenCalled();
  });

  it("va à l'accueil quand aucune page n'était demandée (`/acces` en direct)", async () => {
    // Sur `/acces`, rafraîchir ne ferait que réafficher le formulaire.
    siteAccessLogin.mockResolvedValue(null);
    render(<SiteAccessGate apres="accueil" />);

    await seConnecter("secret-du-club");

    expect(push).toHaveBeenCalledWith("/");
    expect(refresh).not.toHaveBeenCalled();
  });

  it("affiche une erreur sur un mot de passe refusé", async () => {
    siteAccessLogin.mockRejectedValue(new ApiError(401, "Mot de passe incorrect."));
    render(<SiteAccessGate />);

    await seConnecter("mauvais-mot-de-passe");

    expect(await screen.findByRole("alert")).toHaveTextContent(/mot de passe incorrect/i);
    expect(push).not.toHaveBeenCalled();
    expect(refresh).not.toHaveBeenCalled();
  });

  it("affiche un indice de réveil à froid si la connexion dépasse 2,5 s (#622)", async () => {
    vi.useFakeTimers();
    try {
      let resoudre!: () => void;
      siteAccessLogin.mockReturnValue(
        new Promise<null>((resolve) => {
          resoudre = () => resolve(null);
        }),
      );
      render(<SiteAccessGate />);

      fireEvent.change(screen.getByLabelText(/mot de passe/i), {
        target: { value: "secret-du-club" },
      });
      await act(async () => {
        fireEvent.click(screen.getByRole("button", { name: /se connecter/i }));
      });

      expect(screen.queryAllByText(/réveil/i)).toHaveLength(0);
      // Toujours montée : c'est l'apparition du texte, pas de la région, qui doit
      // se voir annoncée (#502 — un lecteur d'écran ignore une région insérée après coup).
      expect(screen.getByRole("status")).toHaveTextContent("");

      await act(async () => {
        vi.advanceTimersByTime(2500);
      });

      expect(screen.queryAllByText(/réveil/i)).toHaveLength(2); // l'indice visible + son annonce sr-only
      expect(screen.getByRole("status")).toHaveTextContent(/réveil/i);

      await act(async () => {
        resoudre();
        await Promise.resolve();
      });

      expect(screen.queryAllByText(/réveil/i)).toHaveLength(0);
    } finally {
      vi.useRealTimers();
    }
  });
});
