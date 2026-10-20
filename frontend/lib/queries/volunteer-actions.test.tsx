import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

const { createVolunteerAction } = vi.hoisted(() => ({ createVolunteerAction: vi.fn() }));
vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { ...original.apiClient, createVolunteerAction } };
});

import { queryKeys } from "./keys";
import { useCreateVolunteerAction } from "./volunteer-actions";

describe("useCreateVolunteerAction", () => {
  it("invalidates my season quota after a declaration", async () => {
    createVolunteerAction.mockResolvedValue({});
    const client = new QueryClient();
    const invalidate = vi.spyOn(client, "invalidateQueries");
    const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
    const { result } = renderHook(() => useCreateVolunteerAction(), { wrapper });

    await act(() => result.current.mutateAsync({ season: 2026, title: "Buvette" } as never));

    expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.mySeasonQuota() });
  });
});
