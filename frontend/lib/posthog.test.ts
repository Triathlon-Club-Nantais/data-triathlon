import { describe, it, expect, vi, beforeEach } from "vitest";

const { capture } = vi.hoisted(() => ({ capture: vi.fn() }));
vi.mock("posthog-js", () => ({ default: { capture } }));

import { captureEvent } from "./posthog";

describe("captureEvent", () => {
  beforeEach(() => {
    capture.mockClear();
    vi.unstubAllEnvs();
  });

  it("délègue à posthog.capture quand le token est présent", () => {
    vi.stubEnv("NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN", "test-token");

    captureEvent("season_changed", { season_count: 1 });

    expect(capture).toHaveBeenCalledWith("season_changed", { season_count: 1 });
  });

  it("ne fait rien sans token, pas de bruit console PostHog", () => {
    vi.stubEnv("NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN", "");

    captureEvent("season_changed", { season_count: 1 });

    expect(capture).not.toHaveBeenCalled();
  });
});
