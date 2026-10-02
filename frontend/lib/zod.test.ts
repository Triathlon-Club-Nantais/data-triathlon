import { globSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { z } from "./zod";

const RACINE = join(import.meta.dirname, "..");

describe("zod configured for a strict CSP (#570)", () => {
  it("disables the JIT, whose eval probe the CSP reports", () => {
    expect(z.config().jitless).toBe(true);
  });

  it("is imported only through lib/zod, so the config always runs first", () => {
    const directs = globSync("{app,components,lib}/**/*.{ts,tsx}", { cwd: RACINE })
      .filter((fichier) => !fichier.endsWith(".test.ts") && !fichier.endsWith(".test.tsx"))
      .filter((fichier) => fichier !== join("lib", "zod.ts"))
      .filter((fichier) => /from\s+["']zod["']/.test(readFileSync(join(RACINE, fichier), "utf8")));

    expect(directs).toEqual([]);
  });
});
