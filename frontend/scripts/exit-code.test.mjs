// @vitest-environment node
import { describe, expect, it } from "vitest";
import { constants } from "node:os";

import { wrapperExitCode } from "./exit-code.mjs";

describe("wrapperExitCode", () => {
  it("propage le code d'une sortie normale", () => {
    expect(wrapperExitCode(0, null)).toBe(0);
    expect(wrapperExitCode(3, null)).toBe(3);
  });

  it("rend 0 quand ni code ni signal ne sont fournis", () => {
    expect(wrapperExitCode(null, null)).toBe(0);
  });

  it("traduit un enfant tué en 128+n plutôt qu'en « 1 »", () => {
    // `pkill -f "next dev"` ou un OOM-kill ne sont pas des pannes applicatives.
    expect(wrapperExitCode(null, "SIGTERM")).toBe(128 + constants.signals.SIGTERM);
    expect(wrapperExitCode(null, "SIGKILL")).toBe(128 + constants.signals.SIGKILL);
    expect(wrapperExitCode(null, "SIGINT")).toBe(130);
  });

  it("le signal prime sur un code résiduel", () => {
    expect(wrapperExitCode(0, "SIGTERM")).toBe(128 + constants.signals.SIGTERM);
  });

  it("se rabat sur 1 pour un signal inconnu de la plateforme", () => {
    expect(wrapperExitCode(null, "SIGPASDECHEZNOUS")).toBe(1);
  });
});
