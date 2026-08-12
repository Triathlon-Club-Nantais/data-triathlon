import { configDefaults, defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./test/setup.ts"],
    // Les exclusions par défaut ne couvrent pas les dossiers en « . » : un
    // worktree créé sous frontend/.claude/ ajoutait sa propre suite à la
    // collecte (52 fichiers de plus, cf. #300). On reprend les défauts, sans
    // quoi node_modules rentrerait.
    exclude: [...configDefaults.exclude, "**/.claude/**"],
  },
  resolve: {
    alias: { "@": path.resolve(__dirname, ".") },
  },
});
