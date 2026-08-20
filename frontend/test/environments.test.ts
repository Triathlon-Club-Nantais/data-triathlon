import { fileURLToPath } from "node:url";
import { glob } from "tinyglobby";
import { configDefaults } from "vitest/config";
import { describe, expect, it } from "vitest";

import config from "../vitest.config";

const ROOT = fileURLToPath(new URL("..", import.meta.url));

type ProjectRead = { name: string; include: string[]; exclude: string[] };

/**
 * Reads the two vitest projects from the config actually in force.
 *
 * On lit la config plutôt qu'une constante partagée : c'est ce que vitest
 * exécute qui doit être vérifié, pas une liste que la config pourrait cesser
 * d'utiliser sans que rien ne rougisse.
 */
function projectsFromConfig(): ProjectRead[] {
  const projects = config.test?.projects;
  if (!projects) {
    throw new Error("vitest.config.ts ne déclare aucun test.projects");
  }
  return projects.map((project) => {
    const test = (project as { test?: Partial<ProjectRead> & { name?: string } }).test;
    if (!test?.name || !test.include || !test.exclude) {
      throw new Error(
        "chaque projet doit déclarer name, include et exclude explicitement" +
          " — le garde-fou ne peut pas vérifier une partition implicite",
      );
    }
    return { name: test.name, include: test.include, exclude: test.exclude };
  });
}

/** Les fichiers que chaque projet réclame, globés avec ses propres motifs. */
async function claims(): Promise<Map<string, string[]>> {
  const byFile = new Map<string, string[]>();
  for (const project of projectsFromConfig()) {
    const files = await glob(project.include, { cwd: ROOT, ignore: project.exclude });
    for (const file of files) {
      byFile.set(file, [...(byFile.get(file) ?? []), project.name]);
    }
  }
  return byFile;
}

describe("partition des fichiers de test entre les projets vitest", () => {
  it("réclame chaque fichier de test par exactement un projet", async () => {
    const byFile = await claims();

    // Référence : le `include` par défaut de **vitest**, importé et non recopié.
    // Une liste d'extensions réécrite à la main (`**/*.test.ts` + `.tsx`)
    // reproduirait l'angle mort qu'on couvre ici — c'est exactement elle qui
    // laisserait les deux scripts/*.test.mjs réclamés par personne.
    const exclusions = config.test?.exclude;
    expect(exclusions, "la config doit porter un exclude commun").toBeDefined();
    const universe = await glob(configDefaults.include, {
      cwd: ROOT,
      ignore: exclusions as string[],
    });

    // Un fichier réclamé par aucun projet ne s'exécute jamais : la suite reste
    // verte en vérifiant un fichier de moins. Le dépôt a déjà payé cette forme
    // de panne (#300), où `npm test` collectait la suite d'un worktree imbriqué.
    const orphans = universe.filter((file) => !byFile.has(file));
    expect(orphans).toEqual([]);

    // Réclamé deux fois, il s'exécute deux fois, dans deux environnements.
    const shared = [...byFile].filter(([, projects]) => projects.length > 1);
    expect(shared).toEqual([]);

    // Garde-fou du garde-fou : un univers vide passerait les deux assertions
    // ci-dessus sans rien vérifier.
    expect(universe.length).toBeGreaterThan(100);
  });

  it("range les deux scripts/*.test.mjs sous node", async () => {
    const byFile = await claims();

    // Ces deux-là sont le piège nommé du sondage : un `grep` restreint aux
    // .ts/.tsx les manque, et ils portent leur annotation en commentaire de
    // ligne. On les cite donc par leur nom.
    expect(byFile.get("scripts/backend-url.test.mjs")).toEqual(["node"]);
    expect(byFile.get("scripts/exit-code.test.mjs")).toEqual(["node"]);
  });
});
