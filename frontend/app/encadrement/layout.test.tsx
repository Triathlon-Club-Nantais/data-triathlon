import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api/client";

const { getSession, listAuthMethods, redirect } = vi.hoisted(() => ({
  getSession: vi.fn(),
  listAuthMethods: vi.fn(),
  redirect: vi.fn(() => {
    throw new Error("NEXT_REDIRECT");
  }),
}));

vi.mock("@/lib/api/server", () => ({
  apiServer: { getSession, listAuthMethods },
}));
vi.mock("next/navigation", () => ({ redirect }));

import SupervisionLayout from "./layout";

const SESSION = {
  id: 1,
  email: "encadrant@exemple.fr",
  display_name: "encadrant",
  created_at: "2026-08-01T14:54:28Z",
  permissions: ["jeunes:read"],
  can_administer: false,
  can_supervise: true,
  roles: [],
  groups: [],
};
const ADMIN_SEUL = { ...SESSION, permissions: ["quality:override"], can_administer: true, can_supervise: false };
const GITHUB = [{ slug: "github", label: "GitHub" }];

describe("Supervision space guard", () => {
  let journal: ReturnType<typeof vi.spyOn>;
  beforeEach(() => {
    vi.clearAllMocks();
    journal = vi.spyOn(console, "error").mockImplementation(() => {});
  });
  afterEach(() => {
    journal.mockRestore();
  });

  it("redirects to /login without a session when login is possible", async () => {
    getSession.mockResolvedValue(null);
    listAuthMethods.mockResolvedValue(GITHUB);
    await expect(SupervisionLayout({ children: <p>secret</p> })).rejects.toThrow("NEXT_REDIRECT");
    expect(redirect).toHaveBeenCalledWith("/login");
  });

  it("renders the children for a supervising session", async () => {
    getSession.mockResolvedValue(SESSION);
    listAuthMethods.mockResolvedValue(GITHUB);
    render(await SupervisionLayout({ children: <p>secret</p> }));
    expect(screen.getByText("secret")).toBeInTheDocument();
  });

  it("refuses in place an administrator without supervision power", async () => {
    getSession.mockResolvedValue(ADMIN_SEUL);
    listAuthMethods.mockResolvedValue(GITHUB);
    render(await SupervisionLayout({ children: <p>secret</p> }));
    expect(screen.queryByText("secret")).toBeNull();
    expect(screen.getByRole("heading", { name: "Encadrement" })).toBeInTheDocument();
    expect(screen.getByText(/aucun écran d'encadrement/)).toBeInTheDocument();
    expect(redirect).not.toHaveBeenCalled();
  });

  it("lets the children through when the backend is unreachable", async () => {
    getSession.mockRejectedValue(new ApiError(502, "Bad Gateway"));
    listAuthMethods.mockRejectedValue(new ApiError(502, "Bad Gateway"));
    render(await SupervisionLayout({ children: <p>secret</p> }));
    expect(screen.getByText("secret")).toBeInTheDocument();
  });
});
