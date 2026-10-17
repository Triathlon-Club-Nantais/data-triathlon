import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { createElement, type ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({ getAdminBadgeCounts: vi.fn() }));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: api };
});

import { useNavBadges } from "./nav-badges";

function wrapperFor(qc: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return createElement(QueryClientProvider, { client: qc }, children);
  };
}

function badges(canAdminister: boolean, qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })) {
  return renderHook(() => useNavBadges(canAdminister), { wrapper: wrapperFor(qc) });
}

beforeEach(() => {
  vi.clearAllMocks();
  api.getAdminBadgeCounts.mockResolvedValue({ identities: 4, feedback: 2 });
});

describe("useNavBadges (#1385)", () => {
  it("fetches every badge in one call", async () => {
    const { result } = badges(true);

    await waitFor(() => expect(result.current.counts.identities).toBe(4));
    expect(result.current.counts.feedback).toBe(2);
    expect(result.current.counts.quality).toBeUndefined();
    expect(api.getAdminBadgeCounts).toHaveBeenCalledTimes(1);
  });

  it("asks nothing of a visitor without admin power", async () => {
    badges(false);

    await new Promise((r) => setTimeout(r, 0));
    expect(api.getAdminBadgeCounts).not.toHaveBeenCalled();
  });

  it("reports loading until the counts arrive", async () => {
    const { result } = badges(true);

    expect(result.current.loading).toBe(true);
    await waitFor(() => expect(result.current.loading).toBe(false));
  });

  it("keeps the counts for 5 minutes: two of them replay a whole review", async () => {
    const qc = new QueryClient();
    const first = badges(true, qc);
    await waitFor(() => expect(first.result.current.loading).toBe(false));
    first.unmount();
    const second = badges(true, qc);
    await waitFor(() => expect(second.result.current.loading).toBe(false));

    expect(api.getAdminBadgeCounts).toHaveBeenCalledTimes(1);
  });

  it("does not import the admin hooks: the root layout would ship all of them (#1559)", () => {
    const source = readFileSync(join(__dirname, "nav-badges.ts"), "utf8");

    expect(source).not.toMatch(/from\s+["'](\.\/admin|@\/lib\/queries\/admin)["']/);
  });
});
