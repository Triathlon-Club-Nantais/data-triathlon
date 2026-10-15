import { readdirSync, readFileSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, it, expect, vi, beforeEach } from "vitest";

const { capture, init } = vi.hoisted(() => ({ capture: vi.fn(), init: vi.fn() }));
vi.mock("posthog-js", () => ({ default: { capture, init, get_explicit_consent_status: () => "pending" } }));

async function freshModule() {
  vi.resetModules();
  return import("./posthog");
}

describe("captureEvent", () => {
  beforeEach(() => {
    capture.mockClear();
    init.mockClear();
    vi.unstubAllEnvs();
    vi.stubEnv("NEXT_PUBLIC_POSTHOG_HOST", "https://eu.posthog.com");
  });

  it("délègue à posthog.capture quand le token est présent", async () => {
    vi.stubEnv("NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN", "test-token");
    const { captureEvent } = await freshModule();

    captureEvent("season_changed", { season_count: 1 });

    await vi.waitFor(() => expect(capture).toHaveBeenCalledWith("season_changed", { season_count: 1 }));
  });

  it("garde les événements émis avant le chargement, dans l'ordre, après init (#1394)", async () => {
    vi.stubEnv("NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN", "test-token");
    const { captureEvent } = await freshModule();

    expect(() => {
      captureEvent("first");
      captureEvent("second");
    }).not.toThrow();
    expect(capture).not.toHaveBeenCalled();

    await vi.waitFor(() => expect(capture).toHaveBeenCalledTimes(2));
    expect(capture.mock.calls.map(([event]) => event)).toEqual(["first", "second"]);
    expect(init).toHaveBeenCalledTimes(1);
    expect(init.mock.invocationCallOrder[0]).toBeLessThan(capture.mock.invocationCallOrder[0]);
  });

  it("appelle posthog.capture sans attendre une fois la bibliothèque chargée (sendBeacon avant navigation)", async () => {
    vi.stubEnv("NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN", "test-token");
    const { captureEvent } = await freshModule();
    captureEvent("warmup");
    await vi.waitFor(() => expect(capture).toHaveBeenCalledTimes(1));

    captureEvent("login_initiated");

    expect(capture).toHaveBeenLastCalledWith("login_initiated");
  });

  it("ne télécharge pas posthog-js sans token, pas de bruit console PostHog", async () => {
    vi.stubEnv("NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN", "");
    let loaded = false;
    vi.resetModules();
    vi.doMock("posthog-js", () => {
      loaded = true;
      return { default: { capture, init } };
    });
    const { captureEvent } = await import("./posthog");

    captureEvent("season_changed", { season_count: 1 });
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(loaded).toBe(false);
    expect(capture).not.toHaveBeenCalled();
  });
});

describe("isPostHogEnabled (#1159)", () => {
  beforeEach(() => vi.unstubAllEnvs());

  it("exige token et hôte, les deux conditions de posthog.init", async () => {
    const { isPostHogEnabled } = await freshModule();
    vi.stubEnv("NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN", "test-token");
    vi.stubEnv("NEXT_PUBLIC_POSTHOG_HOST", "");
    expect(isPostHogEnabled()).toBe(false);

    vi.stubEnv("NEXT_PUBLIC_POSTHOG_HOST", "https://eu.posthog.com");
    expect(isPostHogEnabled()).toBe(true);
  });
});

describe("posthog-js hors du JS initial (#1394)", () => {
  const root = join(__dirname, "..");
  const SKIP = new Set(["node_modules", ".next", "coverage"]);

  function sources(dir: string): string[] {
    return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
      if (SKIP.has(entry.name)) return [];
      const path = join(dir, entry.name);
      if (entry.isDirectory()) return sources(path);
      return /\.tsx?$/.test(entry.name) && !/\.test\.tsx?$/.test(entry.name) ? [path] : [];
    });
  }

  it("aucun fichier n'importe posthog-js statiquement, hors import de types", () => {
    const staticImport = /^\s*(import|export)\s+(?!type\b)[^;]*from\s+["']posthog-js(\/[^"']*)?["']|require\(["']posthog-js/m;
    const offenders = sources(root)
      .filter((path) => staticImport.test(readFileSync(path, "utf8")))
      .map((path) => relative(root, path));
    expect(offenders).toEqual([]);
  });
});
