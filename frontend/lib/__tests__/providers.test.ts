import { describe, expect, it } from "vitest";
import { providerLabel } from "@/lib/constants";

describe("providerLabel", () => {
  it("rend lisible le slug de chaque chronométreur", () => {
    expect(providerLabel("klikego")).toBe("Klikego");
    expect(providerLabel("breizhchrono")).toBe("Breizh Chrono");
    expect(providerLabel("timepulse")).toBe("TimePulse");
    expect(providerLabel("wiclax")).toBe("Wiclax");
    expect(providerLabel("prolivesport")).toBe("ProLiveSport");
    expect(providerLabel("sportinnovation")).toBe("Sport Innovation");
  });

  it("laisse passer un provider inconnu plutôt que de l'effacer", () => {
    expect(providerLabel("chronopuce")).toBe("chronopuce");
  });

  it("libelle « Source » à défaut de provider", () => {
    expect(providerLabel(null)).toBe("Source");
    expect(providerLabel("")).toBe("Source");
  });
});
