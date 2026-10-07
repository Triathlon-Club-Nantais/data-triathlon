import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api/client";

const api = vi.hoisted(() => ({
  countCourses: vi.fn(),
  countQualityQueue: vi.fn(),
  countCourseDuplicates: vi.fn(),
  countPendingProviders: vi.fn(),
  countFeedback: vi.fn(),
  countIdentityReview: vi.fn(),
  countClubMembersToSettle: vi.fn(),
  countPendingVolunteerActions: vi.fn(),
  countBenevoleQueue: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: api };
});

import { useIdentityReviewCount } from "./admin";
import { useNavBadges } from "./nav-badges";

function badges(permissions: string[], canAdminister = permissions.length > 0) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) =>
    createElement(QueryClientProvider, { client: qc }, children);
  return renderHook(() => useNavBadges(new Set(permissions), canAdminister), { wrapper });
}

beforeEach(() => {
  vi.clearAllMocks();
  for (const fn of Object.values(api)) fn.mockResolvedValue({ total: 0 });
  api.countFeedback.mockResolvedValue({ nouveau: 0 });
});

describe("useNavBadges (#1232)", () => {
  it.each([
    ["identities", "athletes:write", api.countIdentityReview],
    ["members", "club_members:manage", api.countClubMembersToSettle],
    ["volunteer", "athletes:volunteer_validate", api.countPendingVolunteerActions],
    ["quality", "quality:override", api.countQualityQueue],
  ])("returns the %s key to whoever holds %s", async (key, permission, count) => {
    count.mockResolvedValue({ total: 7 });

    const { result } = badges([permission]);

    await waitFor(() => expect(result.current.counts[key]).toBe(7));
  });

  it.each([
    ["athletes:write", api.countIdentityReview],
    ["club_members:manage", api.countClubMembersToSettle],
    ["athletes:volunteer_validate", api.countPendingVolunteerActions],
    ["quality:override", api.countQualityQueue],
  ])("asks nothing of whoever lacks %s", async (_permission, count) => {
    const { result } = badges(["feedback:read"]);

    await waitFor(() => expect(result.current.counts.feedback).toBe(0));
    expect(count).not.toHaveBeenCalled();
  });

  it("counts quality on the queue without a human verdict, never on every unreliable course", async () => {
    api.countCourses.mockResolvedValue({ total: 7 });
    api.countQualityQueue.mockResolvedValue({ total: 1 });

    const { result } = badges(["quality:override"]);

    await waitFor(() => expect(result.current.counts.quality).toBe(1));
    expect(api.countCourses).not.toHaveBeenCalled();
  });

  it("counts the volunteer validation queue for an admin account", async () => {
    api.countBenevoleQueue.mockResolvedValue({ total: 3 });

    const { result } = badges(["feedback:read"]);

    await waitFor(() => expect(result.current.counts.validation).toBe(3));
  });

  it("hides the validation queue without the volunteer cookie", async () => {
    api.countBenevoleQueue.mockRejectedValue(new ApiError(401, "Non authentifié"));

    const { result } = badges(["feedback:read"]);

    await waitFor(() => expect(api.countBenevoleQueue).toHaveBeenCalledTimes(1));
    expect(result.current.counts.validation).toBeUndefined();
  });

  it("does not ask for the validation queue for a visitor without admin power", async () => {
    badges([], false);

    await new Promise((r) => setTimeout(r, 0));
    expect(api.countBenevoleQueue).not.toHaveBeenCalled();
  });

  it("keeps the identity review count for 5 minutes: it runs the whole review", async () => {
    const qc = new QueryClient();
    const wrapper = ({ children }: { children: ReactNode }) =>
      createElement(QueryClientProvider, { client: qc }, children);

    const first = renderHook(() => useIdentityReviewCount(), { wrapper });
    await waitFor(() => expect(first.result.current.isSuccess).toBe(true));
    first.unmount();
    const second = renderHook(() => useIdentityReviewCount(), { wrapper });
    await waitFor(() => expect(second.result.current.isSuccess).toBe(true));

    expect(api.countIdentityReview).toHaveBeenCalledTimes(1);
  });
});
