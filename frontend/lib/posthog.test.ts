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

describe("before_send (#1307, #1530)", () => {
  async function beforeSend() {
    vi.stubEnv("NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN", "test-token");
    vi.stubEnv("NEXT_PUBLIC_POSTHOG_HOST", "https://eu.posthog.com");
    init.mockClear();
    const { withPostHog } = await freshModule();
    withPostHog(() => {});
    await vi.waitFor(() => expect(init).toHaveBeenCalled());
    return init.mock.calls[0][1].before_send as (event: unknown) => Record<string, unknown> | null;
  }

  beforeEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("retire query string et fragment de toute URL, à toute profondeur", async () => {
    vi.stubGlobal("window", { location: { pathname: "/resultats" } });
    const send = await beforeSend();
    const page = "https://tcn.test/resultats?name=Jean%20Dupont&seasons=2025#haut";
    const timestamp = new Date();

    const out = send({
      event: "$web_vitals",
      timestamp,
      properties: {
        $current_url: page,
        $referrer: "https://ext.test/p?who=Bob",
        $session_entry_url: page,
        $pathname: "/resultats",
        $web_vitals_LCP_event: { $current_url: page, navigationURL: page, attribution: { url: page } },
        $heatmap_data: { [page]: [{ x: 1 }], "https://tcn.test/resultats?name=Autre": [{ x: 2 }] },
      },
      $set_once: { $initial_current_url: page, $initial_referrer: "$direct", $initial_referring_domain: undefined },
    });

    expect(JSON.stringify(out)).not.toMatch(/Jean|Bob|Autre|seasons|#haut|\?/);
    expect(out?.timestamp).toBe(timestamp);
    const properties = out?.properties as Record<string, unknown>;
    expect(properties.$current_url).toBe("https://tcn.test/resultats");
    expect(properties.$pathname).toBe("/resultats");
    expect(properties.$heatmap_data).toEqual({ "https://tcn.test/resultats": [{ x: 1 }, { x: 2 }] });
    expect(out?.$set_once).toEqual({
      $initial_current_url: "https://tcn.test/resultats",
      $initial_referrer: "$direct",
      $initial_referring_domain: undefined,
    });
  });

  it("retire la query string des liens cliqués (autocapture)", async () => {
    vi.stubGlobal("window", { location: { pathname: "/" } });
    const send = await beforeSend();

    const out = send({
      event: "$autocapture",
      properties: {
        $elements: [{ tag_name: "a", attr__href: "/resultats?name=Jean%20Dupont", $el_text: "Mes résultats" }],
        $elements_chain: 'a:attr__href="/resultats?name=Jean%20Dupont"href="/resultats?name=Jean%20Dupont#x"nth-child="1"',
        $exception_list: [{ stacktrace: { frames: [{ filename: "https://tcn.test/resultats?name=Jean", abs_path: "/p?q=Jean" }] } }],
      },
    });

    expect(JSON.stringify(out)).not.toMatch(/Jean/);
    const properties = out?.properties as Record<string, unknown>;
    expect(properties.$elements).toEqual([{ tag_name: "a", attr__href: "/resultats", $el_text: "Mes résultats" }]);
    expect(properties.$elements_chain).toBe('a:attr__href="/resultats"href="/resultats"nth-child="1"');
  });

  it("jette encore un clic sous /encadrement/jeunes, garde la page vue", async () => {
    vi.stubGlobal("window", { location: { pathname: "/encadrement/jeunes/7" } });
    const send = await beforeSend();

    expect(send({ event: "$autocapture", properties: { $el_text: "Léa" } })).toBeNull();
    expect(send({ event: "$pageview", properties: { $current_url: "https://tcn.test/encadrement/jeunes/7?q=L" } })).toEqual({
      event: "$pageview",
      properties: { $current_url: "https://tcn.test/encadrement/jeunes/7" },
    });
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
