import { beforeEach, describe, expect, it, vi } from "vitest";

const { listAuthMethods, getSession } = vi.hoisted(() => ({
  listAuthMethods: vi.fn(),
  getSession: vi.fn(),
}));

vi.mock("@/lib/api/server", () => ({ apiServer: { listAuthMethods, getSession } }));

import { connexionAdherent } from "./site-access-login";

const GITHUB = [{ slug: "github", label: "GitHub", audience: "admin" }];

describe("connexionAdherent (#1322)", () => {
  beforeEach(() => {
    listAuthMethods.mockReset();
    getSession.mockReset();
  });

  it("propose de se connecter à un anonyme quand un moyen existe", async () => {
    listAuthMethods.mockResolvedValue(GITHUB);
    getSession.mockResolvedValue(null);

    expect(await connexionAdherent()).toBe("proposee");
  });

  it("ne propose rien quand aucun moyen de connexion n'existe", async () => {
    listAuthMethods.mockResolvedValue([]);
    getSession.mockResolvedValue(null);

    expect(await connexionAdherent()).toBeNull();
  });

  it("signale une session connectée non adhérente", async () => {
    listAuthMethods.mockResolvedValue(GITHUB);
    getSession.mockResolvedValue({ is_member: false });

    expect(await connexionAdherent()).toBe("non-adherent");
  });

  it("ne propose rien sur une panne : le formulaire du code reste seul", async () => {
    listAuthMethods.mockRejectedValue(new Error("injoignable"));
    getSession.mockRejectedValue(new Error("injoignable"));

    expect(await connexionAdherent()).toBeNull();
  });
});
