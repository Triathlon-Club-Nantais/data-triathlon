import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

const { init } = vi.hoisted(() => ({ init: vi.fn() }));
vi.mock("posthog-js", () => ({ default: { init } }));

describe("instrumentation-client", () => {
  beforeEach(() => {
    init.mockClear();
    // Le hook s'exécute à l'import : sans reset, seul le premier test le joue.
    vi.resetModules();
    vi.unstubAllEnvs();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("reste silencieux quand les variables PostHog sont absentes", async () => {
    vi.stubEnv("NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN", "");
    vi.stubEnv("NEXT_PUBLIC_POSTHOG_HOST", "");
    const error = vi.spyOn(console, "error").mockImplementation(() => {});
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});

    await import("./instrumentation-client");

    expect(init).not.toHaveBeenCalled();
    expect(error).not.toHaveBeenCalled();
    expect(warn).not.toHaveBeenCalled();
  });

  it("initialise PostHog quand token et host sont présents", async () => {
    vi.stubEnv("NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN", "test-token");
    vi.stubEnv("NEXT_PUBLIC_POSTHOG_HOST", "https://eu.posthog.com");

    await import("./instrumentation-client");

    expect(init).toHaveBeenCalledWith(
      "test-token",
      expect.objectContaining({
        api_host: "/ingest",
        ui_host: "https://eu.posthog.com",
      }),
    );
  });
});
