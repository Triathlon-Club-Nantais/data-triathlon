import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

const { init, optIn, optOut, reset, consentStatus } = vi.hoisted(() => ({
  init: vi.fn(),
  optIn: vi.fn(),
  optOut: vi.fn(),
  reset: vi.fn(),
  consentStatus: vi.fn(() => "pending"),
}));
vi.mock("posthog-js", () => ({
  default: {
    init,
    opt_in_capturing: optIn,
    opt_out_capturing: optOut,
    reset,
    get_explicit_consent_status: consentStatus,
  },
}));

describe("instrumentation-client", () => {
  beforeEach(() => {
    init.mockClear();
    optIn.mockClear();
    optOut.mockClear();
    reset.mockClear();
    consentStatus.mockReturnValue("pending");
    localStorage.clear();
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

  describe("consentement (#1159)", () => {
    beforeEach(() => {
      vi.stubEnv("NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN", "test-token");
      vi.stubEnv("NEXT_PUBLIC_POSTHOG_HOST", "https://eu.posthog.com");
    });

    it("mesure sans cookie ni autocapture tant que le visiteur n'a pas accepté", async () => {
      await import("./instrumentation-client");

      expect(init).toHaveBeenCalledWith(
        "test-token",
        expect.objectContaining({
          cookieless_mode: "on_reject",
          opt_out_capturing_by_default: true,
          autocapture: false,
          disable_session_recording: true,
        }),
      );
      expect(optIn).not.toHaveBeenCalled();
    });

    it("ouvre l'autocapture et confirme l'accord quand le visiteur a accepté", async () => {
      localStorage.setItem("tcn-analytics-consent", JSON.stringify({ choice: "granted", at: Date.now() }));

      await import("./instrumentation-client");

      expect(init).toHaveBeenCalledWith("test-token", expect.objectContaining({ autocapture: true }));
      expect(optIn).toHaveBeenCalledWith({ captureEventName: false });
    });

    it("retire un accord PostHog que le choix du site ne couvre plus (expiré ou effacé)", async () => {
      consentStatus.mockReturnValue("granted");

      await import("./instrumentation-client");

      expect(reset).toHaveBeenCalled();
      expect(optOut).toHaveBeenCalled();
    });
  });
});
