import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, waitFor } from "@testing-library/react";
import { toast } from "sonner";
import { RETOUR_CONNEXION_KEY } from "@/lib/constants";
import type { SessionUser } from "@/lib/types";

const { identify, reset } = vi.hoisted(() => ({ identify: vi.fn(), reset: vi.fn() }));
vi.mock("posthog-js", () => ({ default: { identify, reset, capture: vi.fn() } }));

const { useSession } = vi.hoisted(() => ({ useSession: vi.fn() }));
vi.mock("@/lib/queries/auth", () => ({ useSession }));

vi.mock("sonner", () => ({ toast: { success: vi.fn() } }));

const { replace, pathname } = vi.hoisted(() => ({ replace: vi.fn(), pathname: { value: "/dashboard" } }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
  usePathname: () => pathname.value,
}));

import { Providers } from "./providers";

const SESSION: SessionUser = {
  id: 1,
  email: "contributeur@exemple.fr",
  display_name: "contributeur",
  created_at: "2026-08-01T14:54:28Z",
  permissions: [],
  roles: [],
  groups: [],
};

describe("PostHogSessionSync", () => {
  beforeEach(() => {
    identify.mockClear();
    reset.mockClear();
    vi.stubEnv("NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN", "test-token");
  });

  it("identifie l'utilisateur quand une session existe", () => {
    useSession.mockReturnValue({ data: SESSION });
    render(<Providers>{null}</Providers>);

    expect(identify).toHaveBeenCalledWith("1", expect.objectContaining({ email: SESSION.email }));
    expect(reset).not.toHaveBeenCalled();
  });

  it("réinitialise PostHog quand la session repasse à null, quelle qu'en soit la cause (logout, 401, révocation)", () => {
    useSession.mockReturnValue({ data: SESSION });
    const { rerender } = render(<Providers>{null}</Providers>);
    expect(identify).toHaveBeenCalledTimes(1);

    useSession.mockReturnValue({ data: null });
    rerender(<Providers>{null}</Providers>);

    expect(reset).toHaveBeenCalledTimes(1);
  });

  it("ne réinitialise pas au premier chargement anonyme, rien n'a jamais été identifié", () => {
    useSession.mockReturnValue({ data: null });
    render(<Providers>{null}</Providers>);

    expect(reset).not.toHaveBeenCalled();
  });
});

describe("PostLoginReturn (#494)", () => {
  beforeEach(() => {
    replace.mockClear();
    vi.mocked(toast.success).mockClear();
    sessionStorage.clear();
    pathname.value = "/dashboard";
  });

  it("ramène vers le chemin mémorisé quand il diffère de l'atterrissage, et confirme la connexion", async () => {
    sessionStorage.setItem(RETOUR_CONNEXION_KEY, "/carte");
    useSession.mockReturnValue({ data: SESSION });

    render(<Providers>{null}</Providers>);

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/carte"));
    expect(toast.success).toHaveBeenCalledWith("Connexion réussie");
    expect(sessionStorage.getItem(RETOUR_CONNEXION_KEY)).toBeNull();
  });

  it("ne redirige pas quand aucun retour n'a été mémorisé", () => {
    useSession.mockReturnValue({ data: SESSION });

    render(<Providers>{null}</Providers>);

    expect(replace).not.toHaveBeenCalled();
    expect(toast.success).not.toHaveBeenCalled();
  });

  it("ne redirige pas tant que la session n'est pas connue", () => {
    sessionStorage.setItem(RETOUR_CONNEXION_KEY, "/carte");
    useSession.mockReturnValue({ data: undefined });

    render(<Providers>{null}</Providers>);

    expect(replace).not.toHaveBeenCalled();
    // La clé reste en place : elle doit encore servir une fois la session connue.
    expect(sessionStorage.getItem(RETOUR_CONNEXION_KEY)).toBe("/carte");
  });

  it("efface la clé sans rediriger quand elle vaut déjà le chemin d'atterrissage", () => {
    sessionStorage.setItem(RETOUR_CONNEXION_KEY, "/dashboard");
    useSession.mockReturnValue({ data: SESSION });

    render(<Providers>{null}</Providers>);

    expect(replace).not.toHaveBeenCalled();
    expect(sessionStorage.getItem(RETOUR_CONNEXION_KEY)).toBeNull();
  });
});
