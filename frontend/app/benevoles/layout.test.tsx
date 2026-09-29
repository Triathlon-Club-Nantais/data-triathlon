import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api/client";

const { getSession, getBenevoleQueue } = vi.hoisted(() => ({
  getSession: vi.fn(),
  getBenevoleQueue: vi.fn(),
}));
vi.mock("@/lib/api/server", () => ({ apiServer: { getSession } }));
vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: {
      getBenevoleQueue,
      getBenevoleRejected: vi.fn(() => new Promise(() => {})),
      getValidationQueueHistory: vi.fn(() => new Promise(() => {})),
    },
  };
});
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

import BenevolesLayout from "./layout";
import BenevolesPage from "./page";

beforeEach(() => vi.clearAllMocks());

// #879, « Précision (29/09) » : `/benevoles` (#271) n'est **pas** derrière
// `pages:preview`. Un bénévole sans compte n'a que le mot de passe bénévoles.
describe("BenevolesLayout", () => {
  it("mène un bénévole sans compte au formulaire de mot de passe, sans lire de session", async () => {
    getBenevoleQueue.mockRejectedValue(new ApiError(401, "Non autorisé"));

    render(BenevolesLayout({ children: <BenevolesPage /> }));

    expect(await screen.findByLabelText("Mot de passe")).toBeInTheDocument();
    expect(screen.queryByText("Vous n'avez pas la permission nécessaire")).not.toBeInTheDocument();
    expect(getSession).not.toHaveBeenCalled();
  });
});
