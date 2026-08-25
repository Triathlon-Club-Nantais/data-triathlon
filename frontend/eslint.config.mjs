import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
    // Flat config only ignores node_modules and .git by default, so a worktree
    // nested under frontend/.claude/ would be linted as well (see #300).
    "**/.claude/**",
  ]),
  {
    rules: {
      // Jumeau de `FIX` côté ruff (#591) : le dépôt ne porte aucun marqueur
      // d'intention, et cette règle est ce qui le maintient. Une intention
      // laissée en commentaire n'est ni suivie ni datée ; sa place est une
      // issue. Les quatre termes ci-dessous sont ceux que ruff surveille.
      "no-warning-comments": [
        "error",
        { terms: ["todo", "fixme", "xxx", "hack"], location: "anywhere" },
      ],
    },
  },
]);

export default eslintConfig;
