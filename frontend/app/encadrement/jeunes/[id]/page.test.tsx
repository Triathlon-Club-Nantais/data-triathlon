import { describe, it, expect, vi } from "vitest";

const { notFound } = vi.hoisted(() => ({ notFound: vi.fn() }));

vi.mock("next/navigation", () => ({
  notFound: () => {
    notFound();
    throw new Error("NEXT_HTTP_ERROR_FALLBACK;404");
  },
}));

import AdminJeunePage from "./page";

describe("AdminJeunePage", () => {
  it("traite un identifiant non numérique comme une page introuvable", async () => {
    await expect(AdminJeunePage({ params: Promise.resolve({ id: "abc" }) })).rejects.toThrow();
    expect(notFound).toHaveBeenCalled();
  });
});
