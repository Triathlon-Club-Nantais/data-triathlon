import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, it, expect } from "vitest";

// The barrel is imported by root layout client components (AppNav, UserMenu...),
// so anything it re-exports lands in the first-load JS of every page (#1432).
describe("components/tcn barrel keeps d3 out of the first-load JS (#1432)", () => {
  const barrel = readFileSync(join(__dirname, "index.ts"), "utf8");
  const reexported = [...barrel.matchAll(/from\s+["'](\.[^"']+)["']/g)].map(([, path]) => path);

  it("no re-exported module imports d3", () => {
    const offenders = reexported.filter((path) => {
      const file = [".tsx", ".ts"].map((ext) => join(__dirname, path + ext)).find(existsSync);
      if (!file) throw new Error(`unresolved barrel export ${path}`);
      return /from\s+["']d3(-[^"']*)?["']/.test(readFileSync(file, "utf8"));
    });
    expect(offenders).toEqual([]);
  });
});
