#!/usr/bin/env node
// Lanceur de dev du frontend : découvre le backend du worktree courant, puis
// démarre `next dev` avec BACKEND_URL et API_URL renseignés.
//
// Les deux variables sont lues à des endroits différents — BACKEND_URL par les
// rewrites de next.config.ts (au démarrage) et par la route keep-warm, API_URL par
// les fetch RSC de lib/api/server.ts — d'où l'injection des deux.
//
// Le code applicatif garde sa sémantique `process.env.X || défaut` : rien de ce
// mécanisme de dev n'atteint le build de production.

import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { PORT_FILE_NAME, resolveBackendUrl } from "./backend-url.mjs";

const frontendDir = dirname(dirname(fileURLToPath(import.meta.url)));
const worktreeRoot = dirname(frontendDir);

const { url, source } = await resolveBackendUrl({
  root: worktreeRoot,
  onWait: () =>
    console.log(
      `⏳ En attente du backend de ce worktree (${PORT_FILE_NAME} absent ou port muet)…\n` +
        "   Lancez « task b:dev » dans un autre terminal.",
    ),
});

if (source === "fallback") {
  console.warn(
    `⚠ Backend introuvable : repli sur ${url}. ` +
      "Les appels /api risquent d'échouer — ou de viser le backend d'un autre worktree.",
  );
} else {
  console.log(`✓ Backend : ${url} (${source === "env" ? "BACKEND_URL" : PORT_FILE_NAME})`);
}

const nextBin = join(frontendDir, "node_modules", ".bin", "next");
if (!existsSync(nextBin)) {
  console.error("✗ next introuvable — lancez « npm install » d'abord.");
  process.exit(1);
}

const enfant = spawn(nextBin, ["dev", ...process.argv.slice(2)], {
  cwd: frontendDir,
  stdio: "inherit",
  env: { ...process.env, BACKEND_URL: url, API_URL: url },
});

// Ctrl-C atteint déjà `next` via le groupe de processus ; on relaie SIGTERM
// (arrêt par un superviseur) pour ne pas laisser le serveur orphelin.
process.on("SIGTERM", () => enfant.kill("SIGTERM"));

enfant.on("exit", (code, signal) => {
  process.exit(signal ? 1 : (code ?? 0));
});
