import { existsSync, readFileSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { describe, it, expect } from "vitest";

// The barrel is imported by root layout client components (AppNav, UserMenu...),
// so everything it statically reaches lands in the first-load JS of every page (#1432).
describe("components/tcn barrel keeps d3 out of the first-load JS (#1432)", () => {
  const root = join(__dirname, "..", "..");
  // Static `import`/`export ... from` and side-effect imports; dynamic import() is lazy, so ignored.
  const specifiers = /^\s*(?:import|export)\b[^;]*?["']([^"']+)["']/gm;

  function resolve(from: string, specifier: string): string | undefined {
    const base = specifier.startsWith("@/")
      ? join(root, specifier.slice(2))
      : specifier.startsWith(".") ? join(dirname(from), specifier) : undefined;
    if (!base) return undefined;
    const candidates = [".tsx", ".ts", "/index.tsx", "/index.ts"].map((ext) => base + ext);
    const file = candidates.find(existsSync);
    if (!file) throw new Error(`unresolved import ${specifier} in ${relative(root, from)}`);
    return file;
  }

  it("nothing the barrel statically reaches imports d3", () => {
    const seen = new Set<string>();
    const offenders = new Set<string>();
    const queue = [join(__dirname, "index.ts")];
    while (queue.length) {
      const file = queue.pop()!;
      if (seen.has(file)) continue;
      seen.add(file);
      for (const [, specifier] of readFileSync(file, "utf8").matchAll(specifiers)) {
        if (/^d3(-|$)/.test(specifier)) offenders.add(relative(root, file));
        const next = resolve(file, specifier);
        if (next) queue.push(next);
      }
    }
    expect([...offenders]).toEqual([]);
  });
});
