import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Le seul chemin de déploiement est la CLI de `deploy.yml` (#1589) : chaque
 * déploiement créé par l'intégration Git, même annulé, compte dans le quota
 * gratuit de 100 par jour.
 */
describe("vercel.json", () => {
  const config = JSON.parse(
    readFileSync(path.join(__dirname, "vercel.json"), "utf8"),
  );

  it("disables Git-triggered deployments on every branch", () => {
    expect(config.git.deploymentEnabled).toBe(false);
  });

  it("carries no build setting that would change the CLI build", () => {
    expect(Object.keys(config).sort()).toEqual(["$schema", "git"]);
  });
});
