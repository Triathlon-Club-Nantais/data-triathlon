import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { SessionUser } from "@/lib/types";
import BenevolatPage from "./page";

const { useSession, push } = vi.hoisted(() => ({
  useSession: vi.fn(),
  push: vi.fn(),
}));

vi.mock("@/lib/queries/auth", () => ({ useSession }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

vi.mock("@/components/benevolat/VolunteerActionForm", () => ({
  VolunteerActionForm: () => <div data-testid="volunteer-action-form" />,
}));
vi.mock("@/components/benevolat/VolunteerDeclarationForm", () => ({
  VolunteerDeclarationForm: () => <div data-testid="volunteer-declaration-form" />,
}));
vi.mock("@/components/benevolat/VolunteerDeclarationList", () => ({
  VolunteerDeclarationList: () => <div data-testid="volunteer-declaration-list" />,
}));

function session(): SessionUser {
  return {
    id: 1,
    email: "adherent@exemple.fr",
    display_name: "Adhérent",
    created_at: "2026-01-01T00:00:00Z",
    permissions: [],
    roles: [],
  } as unknown as SessionUser;
}

describe("BenevolatPage — ouverture au mot de passe du site (#809)", () => {
  it("affiche le formulaire de crédit d'un athlète sans session SSO", () => {
    useSession.mockReturnValue({ data: null, isPending: false });

    render(<BenevolatPage />);

    expect(screen.getByTestId("volunteer-action-form")).toBeInTheDocument();
  });

  it("invite à se connecter pour l'auto-déclaration sans session SSO", () => {
    useSession.mockReturnValue({ data: null, isPending: false });

    render(<BenevolatPage />);

    expect(screen.getByRole("button", { name: /se connecter/i })).toBeInTheDocument();
    expect(screen.queryByTestId("volunteer-declaration-form")).not.toBeInTheDocument();
  });

  it("affiche les deux sections avec une session SSO", () => {
    useSession.mockReturnValue({ data: session(), isPending: false });

    render(<BenevolatPage />);

    expect(screen.getByTestId("volunteer-action-form")).toBeInTheDocument();
    expect(screen.getByTestId("volunteer-declaration-form")).toBeInTheDocument();
    expect(screen.getByTestId("volunteer-declaration-list")).toBeInTheDocument();
  });

  it("n'affiche rien pendant la résolution de la session, hors formulaire de crédit", () => {
    useSession.mockReturnValue({ data: undefined, isPending: true });

    render(<BenevolatPage />);

    expect(screen.getByTestId("volunteer-action-form")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /se connecter/i })).not.toBeInTheDocument();
    expect(screen.queryByTestId("volunteer-declaration-form")).not.toBeInTheDocument();
  });
});
