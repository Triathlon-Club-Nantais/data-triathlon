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

import { useNavBadges } from "./nav-badges";

function badges(pouvoirs: string[], peutAdministrer = pouvoirs.length > 0) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) =>
    createElement(QueryClientProvider, { client: qc }, children);
  return renderHook(() => useNavBadges(new Set(pouvoirs), peutAdministrer), { wrapper });
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
  ])("rend la clé %s pour qui porte %s", async (cle, pouvoir, compter) => {
    compter.mockResolvedValue({ total: 7 });

    const { result } = badges([pouvoir]);

    await waitFor(() => expect(result.current[cle]).toBe(7));
  });

  it.each([
    ["athletes:write", api.countIdentityReview],
    ["club_members:manage", api.countClubMembersToSettle],
    ["athletes:volunteer_validate", api.countPendingVolunteerActions],
    ["quality:override", api.countQualityQueue],
  ])("ne demande rien à qui ne porte pas %s", async (_pouvoir, compter) => {
    const { result } = badges(["feedback:read"]);

    await waitFor(() => expect(result.current.feedback).toBe(0));
    expect(compter).not.toHaveBeenCalled();
  });

  it("compte la qualité sur la file sans avis humain, jamais sur toutes les épreuves non fiables", async () => {
    api.countCourses.mockResolvedValue({ total: 7 });
    api.countQualityQueue.mockResolvedValue({ total: 1 });

    const { result } = badges(["quality:override"]);

    await waitFor(() => expect(result.current.quality).toBe(1));
    expect(api.countCourses).not.toHaveBeenCalled();
  });

  it("compte la file de validation des épreuves pour un compte d'administration", async () => {
    api.countBenevoleQueue.mockResolvedValue({ total: 3 });

    const { result } = badges(["feedback:read"]);

    await waitFor(() => expect(result.current.validation).toBe(3));
  });

  it("tait la file de validation sans cookie bénévoles", async () => {
    api.countBenevoleQueue.mockRejectedValue(new ApiError(401, "Non authentifié"));

    const { result } = badges(["feedback:read"]);

    await waitFor(() => expect(api.countBenevoleQueue).toHaveBeenCalledTimes(1));
    expect(result.current.validation).toBeUndefined();
  });

  it("ne demande pas la file de validation à un visiteur sans pouvoir d'administration", async () => {
    badges([], false);

    await new Promise((r) => setTimeout(r, 0));
    expect(api.countBenevoleQueue).not.toHaveBeenCalled();
  });
});
