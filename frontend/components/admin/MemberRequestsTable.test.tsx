import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { MemberRequestReview } from "@/lib/types";

const { getMemberRequests, approveMemberRequest, rejectMemberRequest } = vi.hoisted(() => ({
  getMemberRequests: vi.fn(),
  approveMemberRequest: vi.fn(),
  rejectMemberRequest: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { getMemberRequests, approveMemberRequest, rejectMemberRequest } };
});

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

import { MemberRequestsTable } from "./MemberRequestsTable";

const DEMANDE: MemberRequestReview = {
  id: 7,
  created_at: "2026-10-17T10:00:00Z",
  first_name: "Léa",
  last_name: "Martin",
  birth_date: "1990-03-05",
  phone: "0601020304",
  user: { id: 12, display_name: "Léa M.", email: "lea@exemple.fr" },
};

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemberRequestsTable />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  getMemberRequests.mockReset();
  approveMemberRequest.mockReset();
  rejectMemberRequest.mockReset();
});

describe("MemberRequestsTable (#1785)", () => {
  it("lists requests with birth date and phone", async () => {
    getMemberRequests.mockResolvedValue([DEMANDE]);
    afficher();
    expect(await screen.findByText("Léa Martin")).toBeInTheDocument();
    expect(screen.getByText("05/03/1990")).toBeInTheDocument();
    expect(screen.getByText("0601020304")).toBeInTheDocument();
    expect(screen.getByText("lea@exemple.fr")).toBeInTheDocument();
  });

  it("says when birth date and phone are missing", async () => {
    getMemberRequests.mockResolvedValue([{ ...DEMANDE, birth_date: null, phone: null }]);
    afficher();
    expect(await screen.findByText("Non renseignée")).toBeInTheDocument();
    expect(screen.getByText("Non renseigné")).toBeInTheDocument();
  });

  it("approves a request", async () => {
    getMemberRequests.mockResolvedValue([DEMANDE]);
    approveMemberRequest.mockResolvedValue(null);
    afficher();
    await userEvent.click(await screen.findByRole("button", { name: /Valider/ }));
    expect(approveMemberRequest).toHaveBeenCalledWith(7);
  });

  it("rejects a request", async () => {
    getMemberRequests.mockResolvedValue([DEMANDE]);
    rejectMemberRequest.mockResolvedValue(null);
    afficher();
    await userEvent.click(await screen.findByRole("button", { name: /Refuser/ }));
    expect(rejectMemberRequest).toHaveBeenCalledWith(7);
  });

  it("says when there is no request", async () => {
    getMemberRequests.mockResolvedValue([]);
    afficher();
    expect(await screen.findByText("Aucune demande d'adhésion en attente.")).toBeInTheDocument();
  });
});
