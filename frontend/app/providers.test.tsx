import { describe, it, expect, vi, beforeEach } from "vitest";
import { render } from "@testing-library/react";
import type { SessionUser } from "@/lib/types";

const { identify, reset } = vi.hoisted(() => ({ identify: vi.fn(), reset: vi.fn() }));
vi.mock("posthog-js", () => ({ default: { identify, reset, capture: vi.fn() } }));

const { useSession } = vi.hoisted(() => ({ useSession: vi.fn() }));
vi.mock("@/lib/queries/auth", () => ({ useSession }));

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
