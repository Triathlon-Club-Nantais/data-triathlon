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
vi.mock("next/navigation", async (importOriginal) => ({
  ...(await importOriginal<typeof import("next/navigation")>()),
  redirect,
}));

import AccountLayout from "./layout";

const SESSION = {
  id: 1,
  email: "membre@exemple.fr",
  display_name: "membre",
  created_at: "2026-08-01T14:54:28Z",
  permissions: [],
  can_administer: false,
  can_supervise: false,
  roles: [],
  groups: [],
};
const GITHUB = [{ slug: "github", label: "GitHub" }];

describe("Account page guard", () => {
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
    await expect(AccountLayout({ children: <p>secret</p> })).rejects.toThrow("NEXT_REDIRECT");
    expect(redirect).toHaveBeenCalledWith("/login");
  });

  it("renders the children for any signed-in session", async () => {
    getSession.mockResolvedValue(SESSION);
    listAuthMethods.mockResolvedValue(GITHUB);
    render(await AccountLayout({ children: <p>secret</p> }));
    expect(screen.getByText("secret")).toBeInTheDocument();
  });

  it("lets the children through when the backend is unreachable", async () => {
    getSession.mockRejectedValue(new ApiError(502, "Bad Gateway"));
    listAuthMethods.mockRejectedValue(new ApiError(502, "Bad Gateway"));
    render(await AccountLayout({ children: <p>secret</p> }));
    expect(screen.getByText("secret")).toBeInTheDocument();
  });
});
