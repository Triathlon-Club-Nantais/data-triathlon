#!/usr/bin/env node
// Lanceur de dev du frontend : découvre le backend du worktree courant, puis
// démarre `next dev` avec BACKEND_URL et API_URL renseignés.
//
// Les deux variables sont lues à des endroits différents — BACKEND_URL par les
// rewrites de next.config.ts (au démarrage) et par la route keep-warm, API_URL par
// les fetch RSC de lib/api/server.ts — d'où l'injection des deux.
//
// La découverte ne fait que **combler** : une valeur déjà posée par l'opérateur
// gagne, et les `.env*` comptent autant que le shell — c'est le loader de Next
// lui-même (@next/env) qui les lit ici, pour que la précédence ne diverge pas.
// Sans cela, injecter les deux variables aurait rendu `.env.local` muet (Next ne
// fait jamais primer un fichier .env sur l'environnement qu'il reçoit).
//
// Le code applicatif garde sa sémantique `process.env.X || défaut` : rien de ce
// mécanisme de dev n'atteint le build de production.

import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

// @next/env est du CommonJS sans exports nommés détectables : import par défaut obligé.
import nextEnv from "@next/env";

import { PORT_FILE_NAME, missingBackendEnv, resolveBackendUrl } from "./backend-url.mjs";
import { wrapperExitCode } from "./exit-code.mjs";

const frontendDir = dirname(dirname(fileURLToPath(import.meta.url)));
const worktreeRoot = dirname(frontendDir);

// `loadEnvConfig` peuple aussi notre process.env ; on garde l'environnement reçu
// pour le transmettre tel quel à l'enfant, qui refera ce chargement lui-même.
const envRecu = { ...process.env };
const { combinedEnv } = nextEnv.loadEnvConfig(frontendDir, true);

const { url, source } = await resolveBackendUrl({
  env: combinedEnv,
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

const injecte = missingBackendEnv(combinedEnv, url);

const nextBin = join(frontendDir, "node_modules", ".bin", "next");
if (!existsSync(nextBin)) {
  console.error("✗ next introuvable — lancez « npm install » d'abord.");
  process.exit(1);
}

const enfant = spawn(nextBin, ["dev", ...process.argv.slice(2)], {
  cwd: frontendDir,
  stdio: "inherit",
  env: { ...envRecu, ...injecte },
});

// Ctrl-C atteint déjà `next` via le groupe de processus ; on relaie SIGTERM
// (arrêt par un superviseur) pour ne pas laisser le serveur orphelin.
process.on("SIGTERM", () => enfant.kill("SIGTERM"));

// On rend le sort de l'enfant, signal compris (128+n) : un « 1 » forfaitaire ferait
// passer un `pkill` ou un OOM-kill pour une panne applicative. Cf. exit-code.mjs.
enfant.on("exit", (code, signal) => {
  process.exit(wrapperExitCode(code, signal));
});
