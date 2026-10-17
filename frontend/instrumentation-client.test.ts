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

// posthog-js se charge après coup (#1394) : on attend son init.
async function loadInstrumentation() {
  await import("./instrumentation-client");
  await vi.waitFor(() => expect(init).toHaveBeenCalled());
}

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
    await new Promise((resolve) => setTimeout(resolve, 10));

    expect(init).not.toHaveBeenCalled();
    expect(error).not.toHaveBeenCalled();
    expect(warn).not.toHaveBeenCalled();
  });

  it("pose le cookie d'accord avant tout chargement de posthog-js (#1394)", async () => {
    vi.stubEnv("NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN", "test-token");
    vi.stubEnv("NEXT_PUBLIC_POSTHOG_HOST", "https://eu.posthog.com");
    localStorage.setItem("tcn-analytics-consent", JSON.stringify({ choice: "granted", at: Date.now() }));

    await import("./instrumentation-client");

    expect(document.cookie).toContain("tcn_analytics_consent=granted");
    expect(init).not.toHaveBeenCalled();
    await vi.waitFor(() => expect(init).toHaveBeenCalled());
  });

  it("initialise PostHog quand token et host sont présents", async () => {
    vi.stubEnv("NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN", "test-token");
    vi.stubEnv("NEXT_PUBLIC_POSTHOG_HOST", "https://eu.posthog.com");

    await loadInstrumentation();

    expect(init).toHaveBeenCalledWith(
      "test-token",
      expect.objectContaining({
        api_host: "/ingest",
        ui_host: "https://eu.posthog.com",
      }),
    );
  });

  it("capture les Core Web Vitals, sans dépendre du réglage distant du projet (#1318)", async () => {
    vi.stubEnv("NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN", "test-token");
    vi.stubEnv("NEXT_PUBLIC_POSTHOG_HOST", "https://eu.posthog.com");

    await loadInstrumentation();

    expect(init).toHaveBeenCalledWith(
      "test-token",
      expect.objectContaining({ capture_performance: expect.objectContaining({ web_vitals: true }) }),
    );
  });

  describe("consentement (#1159)", () => {
    beforeEach(() => {
      vi.stubEnv("NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN", "test-token");
      vi.stubEnv("NEXT_PUBLIC_POSTHOG_HOST", "https://eu.posthog.com");
    });

    it("mesure sans cookie ni autocapture tant que le visiteur n'a pas accepté", async () => {
      await loadInstrumentation();

      expect(init).toHaveBeenCalledWith(
        "test-token",
        expect.objectContaining({
          cookieless_mode: "on_reject",
          opt_out_capturing_by_default: true,
          autocapture: false,
          capture_heatmaps: false,
          capture_dead_clicks: false,
          disable_session_recording: true,
        }),
      );
      expect(optIn).not.toHaveBeenCalled();
    });

    it("ouvre l'autocapture et confirme l'accord quand le visiteur a accepté", async () => {
      localStorage.setItem("tcn-analytics-consent", JSON.stringify({ choice: "granted", at: Date.now() }));

      await loadInstrumentation();

      expect(init).toHaveBeenCalledWith("test-token", expect.objectContaining({ autocapture: true }));
      expect(optIn).toHaveBeenCalledWith({ captureEventName: false });
    });

    it("retire un accord PostHog que le choix du site ne couvre plus (expiré ou effacé)", async () => {
      consentStatus.mockReturnValue("granted");

      await loadInstrumentation();

      expect(reset).toHaveBeenCalled();
      expect(optOut).toHaveBeenCalled();
    });
  });

  describe("écrans jeunes exclus de l'autocapture (#1307)", () => {
    type Event = { event: string; properties?: Record<string, unknown> };
    type BeforeSend = (event: Event | null) => Event | null;

    async function beforeSendAt(path: string): Promise<BeforeSend> {
      vi.stubEnv("NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN", "test-token");
      vi.stubEnv("NEXT_PUBLIC_POSTHOG_HOST", "https://eu.posthog.com");
      window.history.pushState({}, "", path);
      await loadInstrumentation();
      return init.mock.calls[0][1].before_send;
    }

    afterEach(() => window.history.pushState({}, "", "/"));

    const elements = [{ tag_name: "a", $el_text: "Alix Martin", attr__href: "/encadrement/jeunes/42" }];
    const carriesAName: Event[] = [
      { event: "$autocapture", properties: { $elements: elements, $el_text: "Alix Martin" } },
      { event: "$rageclick", properties: { $elements: elements } },
      { event: "$dead_click", properties: { $elements: elements } },
      { event: "$dead_swipe", properties: { $elements: elements } },
      { event: "$future_element_event", properties: { $elements_chain: 'a:text="Alix Martin"' } },
      { event: "$copy_autocapture", properties: { $selected_content: "Alix Martin" } },
      { event: "$exception", properties: { $exception_list: [{ value: "Alix Martin introuvable" }] } },
    ];

    it.each(["/encadrement/jeunes", "/encadrement/jeunes/42", "/encadrement/jeunes/appel", "/encadrement/jeunes/groupes"])(
      "écarte tout événement porteur d'un élément, d'une copie ou d'une erreur sous %s",
      async (path) => {
        const beforeSend = await beforeSendAt(path);
        for (const event of carriesAName) {
          expect(beforeSend(event), event.event).toBeNull();
        }
      },
    );

    it("laisse passer pages vues et événements métier sans élément sur les écrans jeunes", async () => {
      const beforeSend = await beforeSendAt("/encadrement/jeunes/42");
      const pageview = { event: "$pageview", properties: { $current_url: "/encadrement/jeunes/42" } };
      const custom = { event: "profile_created", properties: { source: "form" } };
      expect(beforeSend(pageview)).toEqual(pageview);
      expect(beforeSend(custom)).toEqual(custom);
      expect(beforeSend(null)).toBeNull();
    });

    it.each(["/", "/admin/courses", "/encadrement/jeunesse"])("ne jette rien sous %s", async (path) => {
      const beforeSend = await beforeSendAt(path);
      for (const event of carriesAName) {
        expect(beforeSend(event), event.event).toEqual(event);
      }
    });
  });
});
