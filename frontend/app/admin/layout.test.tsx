import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const { serverFetchAuthed, redirect } = vi.hoisted(() => ({
  serverFetchAuthed: vi.fn(),
  redirect: vi.fn(() => {
    // `redirect()` de Next interrompt le rendu en levant : le simuler à
    // l'identique est ce qui prouve que rien n'est rendu après la garde.
    throw new Error("NEXT_REDIRECT");
  }),
}));

vi.mock("@/lib/api/server", () => ({ apiServer: { getSession: serverFetchAuthed } }));
vi.mock("next/navigation", () => ({ redirect }));

import AdminLayout from "./layout";

describe("Garde des écrans d'administration (FR-040)", () => {
  it("redirige vers /login sans session", async () => {
    serverFetchAuthed.mockResolvedValue(null);

    await expect(AdminLayout({ children: <p>secret</p> })).rejects.toThrow("NEXT_REDIRECT");
    expect(redirect).toHaveBeenCalledWith("/login");
  });

  it("rend les enfants avec une session valide", async () => {
    serverFetchAuthed.mockResolvedValue({
      id: 1,
      email: "contributeur@exemple.fr",
      display_name: "contributeur",
      created_at: "2026-08-01T14:54:28Z",
    });

    render(await AdminLayout({ children: <p>contenu réservé</p> }));

    expect(screen.getByText("contenu réservé")).toBeInTheDocument();
  });

  it("valide réellement la session, plutôt que de constater un cookie", async () => {
    // Un `middleware.ts` ne peut voir que la **présence** du cookie : il
    // laisserait passer une session révoquée ou expirée. La garde appelle donc
    // l'API, dont la réponse porte l'invariant à trois conditions.
    serverFetchAuthed.mockResolvedValue(null);

    await expect(AdminLayout({ children: <p>secret</p> })).rejects.toThrow();
    expect(serverFetchAuthed).toHaveBeenCalled();
  });
});
