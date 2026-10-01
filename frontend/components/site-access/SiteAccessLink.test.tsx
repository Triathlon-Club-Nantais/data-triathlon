import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SiteAccessLink } from "./SiteAccessLink";

vi.mock("next/navigation", () => ({ usePathname: () => "/admin/utilisateurs" }));

describe("SiteAccessLink", () => {
  it("mène à la saisie du code, avec l'écran courant comme retour", () => {
    render(<SiteAccessLink />);

    expect(screen.getByRole("link", { name: "Saisir le code d'accès" })).toHaveAttribute(
      "href",
      "/acces?retour=%2Fadmin%2Futilisateurs",
    );
  });
});
