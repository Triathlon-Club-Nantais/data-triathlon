import { configDefaults, defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";

// Les seuls fichiers de test qui ont besoin d'un DOM : tous les `.test.tsx`,
// plus trois `.test.ts` nommés un par un. Tout le reste tourne sous `node`, 4x
// plus rapide sur cette tranche (8 s → 2 s sur 27 fichiers).
//
// Le défaut est `node` à cause du **mode de défaillance**, pas de la vitesse :
// un test à DOM qui atterrit là échoue tout de suite sur « document is not
// defined ». Avec jsdom par défaut, l'oubli inverse est silencieux — le test
// passe, et coûte une seconde par exécution, pour toujours.
const GLOBS_JSDOM = [
  "**/*.test.tsx",
  "hooks/useRescrapeStream.test.ts",
  "lib/queries/admin.test.ts",
  "lib/queries/auth.test.ts",
];

// Les exclusions par défaut ne couvrent pas les dossiers en « . » : un
// worktree créé sous frontend/.claude/ ajoutait sa propre suite à la
// collecte (52 fichiers de plus, cf. #300). On reprend les défauts, sans
// quoi node_modules rentrerait.
const EXCLUDE = [...configDefaults.exclude, "**/.claude/**"];

// Ne rien exporter d'autre que ce `default` : un export nommé fait émettre à
// rollup un avertissement MIXED_EXPORTS à chaque exécution de la suite.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, ".") },
  },
  test: {
    globals: true,
    setupFiles: ["./test/setup.ts"],
    exclude: EXCLUDE,
    // `environmentMatchGlobs` a été **supprimé** de vitest 4 (pas déprécié) :
    // `projects` est la seule route. `extends: true` fait hériter chaque projet
    // des `plugins`, du `resolve.alias` et des options `test` ci-dessus.
    projects: [
      {
        extends: true,
        test: {
          name: "jsdom",
          environment: "jsdom",
          include: GLOBS_JSDOM,
          exclude: EXCLUDE,
        },
      },
      {
        extends: true,
        test: {
          name: "node",
          environment: "node",
          // `node` prend le `include` par défaut de vitest **moins** les globs
          // jsdom. La partition est ainsi *structurelle* : tout fichier que
          // vitest collecte tombe dans exactement un projet. Deux listes
          // disjointes tenues à la main donneraient le même résultat aujourd'hui
          // et divergeraient au premier ajout — `test/environments.test.ts` est
          // là pour que cette divergence rougisse.
          include: configDefaults.include,
          exclude: [...EXCLUDE, ...GLOBS_JSDOM],
        },
      },
    ],
  },
});
