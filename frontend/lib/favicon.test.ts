import { describe, it, expect, beforeEach, vi } from "vitest";

describe("getFaviconColor", () => {
  beforeEach(() => {
    vi.unstubAllEnvs();
  });

  it("retourne l'orange de marque quand FAVICON_VARIANT est absente (prod, local)", async () => {
    const { getFaviconColor, FAVICON_COLOR_PROD } = await import("./favicon");
    expect(getFaviconColor(process.env.FAVICON_VARIANT)).toBe(FAVICON_COLOR_PROD);
  });

  it("retourne le violet de preview quand FAVICON_VARIANT vaut 'preview'", async () => {
    const { getFaviconColor, FAVICON_COLOR_PREVIEW } = await import("./favicon");
    expect(getFaviconColor("preview")).toBe(FAVICON_COLOR_PREVIEW);
  });

  it("retourne l'orange de marque pour toute valeur inconnue", async () => {
    const { getFaviconColor, FAVICON_COLOR_PROD } = await import("./favicon");
    expect(getFaviconColor("staging")).toBe(FAVICON_COLOR_PROD);
  });
});
