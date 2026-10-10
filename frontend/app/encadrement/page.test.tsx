import { beforeEach, describe, expect, it, vi } from "vitest";

const { getSession, redirect } = vi.hoisted(() => ({
  getSession: vi.fn(),
  redirect: vi.fn((href: string) => {
    throw new Error(`NEXT_REDIRECT ${href}`);
  }),
}));

vi.mock("@/lib/api/server", () => ({ apiServer: { getSession } }));
vi.mock("next/navigation", () => ({ redirect }));

import SupervisionHome from "./page";

beforeEach(() => {
  redirect.mockClear();
});

describe("/encadrement", () => {
  it.each([
    [["jeunes:read"], "/encadrement/jeunes"],
    [["athletes:volunteer_validate", "pages:preview"], "/encadrement/benevolat"],
  ])("redirects %j to the first open screen %s", async (permissions, href) => {
    getSession.mockResolvedValue({ permissions });
    await expect(SupervisionHome()).rejects.toThrow("NEXT_REDIRECT");
    expect(redirect).toHaveBeenCalledWith(href);
  });

  it("falls back to the first screen when the session is unreadable", async () => {
    getSession.mockRejectedValue(new Error("backend down"));
    await expect(SupervisionHome()).rejects.toThrow("NEXT_REDIRECT");
    expect(redirect).toHaveBeenCalledWith("/encadrement/jeunes");
  });
});
