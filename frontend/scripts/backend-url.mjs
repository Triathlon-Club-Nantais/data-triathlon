// Découverte du backend de dev du worktree courant.
//
// Plusieurs worktrees du dépôt tournent en parallèle. `next dev` choisit tout seul
// un port libre (3000, 3001…), mais les rewrites `/api/*` (next.config.ts) et les
// fetch RSC (lib/api/server.ts) se rabattaient sur `localhost:8001` en dur : le
// front d'un worktree lisait donc la base d'un autre, sans la moindre erreur.
//
// `backend/scripts/dev_server.py` publie son port dans `.dev-backend.json` à la
// racine du worktree ; on le lit ici pour alimenter BACKEND_URL et API_URL.

import { readFile } from "node:fs/promises";
import { createConnection } from "node:net";
import { join } from "node:path";

export const PORT_FILE_NAME = ".dev-backend.json";

/** Cible de **connexion** vers le backend, jamais une adresse d'écoute : ce module ne
 *  bind rien (`next dev` écoute de son côté `0.0.0.0` par défaut). D'où le loopback et
 *  non `0.0.0.0`, qui ne désigne aucune destination — seul Linux la tolère en `connect()`.
 *  Backend hors de la machine (conteneur, autre hôte) : passer `BACKEND_URL`. */
const CLIENT_HOST = "127.0.0.1";

export const DEFAULT_BACKEND_URL = `http://${CLIENT_HOST}:8001`;

/** Les deux variables qui portent la cible du backend, lues à des endroits distincts :
 *  `BACKEND_URL` par les rewrites de `next.config.ts`, `API_URL` par les fetch RSC de
 *  `lib/api/server.ts`. En prod (Vercel) elles peuvent viser des cibles différentes. */
export const BACKEND_ENV_KEYS = ["BACKEND_URL", "API_URL"];

const PROBE_TIMEOUT_MS = 300;
const DEFAULT_TIMEOUT_MS = 60_000;
const DEFAULT_POLL_MS = 500;

/** Charge publiée par le backend, ou null si absente ou illisible. */
export async function readPublishedBackend(root) {
  try {
    const brut = await readFile(join(root, PORT_FILE_NAME), "utf-8");
    const charge = JSON.parse(brut);
    if (typeof charge?.port !== "number") return null;
    return { port: charge.port, url: charge.url ?? `http://${CLIENT_HOST}:${charge.port}` };
  } catch {
    return null;
  }
}

/** Vrai si quelque chose écoute sur ce port.
 *
 * C'est ce test qui rend la découverte auto-corrigeante : un backend tué par
 * `kill -9` laisse son fichier derrière lui, et le suivre proxyfierait dans le vide.
 */
export function isPortAlive(port, host = CLIENT_HOST, timeoutMs = PROBE_TIMEOUT_MS) {
  return new Promise((resolve) => {
    const socket = createConnection({ port, host });
    const conclure = (vivant) => {
      socket.destroy();
      resolve(vivant);
    };
    socket.setTimeout(timeoutMs);
    socket.once("connect", () => conclure(true));
    socket.once("timeout", () => conclure(false));
    socket.once("error", () => conclure(false));
  });
}

const attendre = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * URL du backend à utiliser, par ordre de priorité :
 *   1. `BACKEND_URL` de l'environnement (source "env") — aucune attente ;
 *   2. le port publié par le backend du worktree, s'il répond (source "file") ;
 *   3. après `timeoutMs`, le port par défaut (source "fallback").
 *
 * L'attente permet de lancer le front avant le backend, dans n'importe quel ordre
 * et dans des terminaux séparés.
 */
export async function resolveBackendUrl({
  env = process.env,
  root,
  timeoutMs = DEFAULT_TIMEOUT_MS,
  pollMs = DEFAULT_POLL_MS,
  onWait,
} = {}) {
  const impose = env.BACKEND_URL?.trim();
  if (impose) return { url: impose, source: "env" };

  const echeance = Date.now() + timeoutMs;
  let signale = false;

  do {
    const publie = await readPublishedBackend(root);
    if (publie && (await isPortAlive(publie.port))) {
      return { url: publie.url, source: "file" };
    }
    if (!signale) {
      signale = true;
      onWait?.();
    }
    if (Date.now() >= echeance) break;
    await attendre(pollMs);
  } while (Date.now() < echeance);

  return { url: DEFAULT_BACKEND_URL, source: "fallback" };
}

/**
 * Variables à injecter dans `next dev` : **seulement** celles que personne n'a définies.
 *
 * Écraser une valeur fournie (shell ou `.env*`) retirerait la seule façon de dissocier
 * la cible SSR (`API_URL`) de celle des rewrites (`BACKEND_URL`) — et rendrait muet un
 * `.env.local`, que Next ne fait justement jamais primer sur l'environnement reçu.
 */
export function missingBackendEnv(env, url) {
  return Object.fromEntries(
    BACKEND_ENV_KEYS.filter((cle) => !env[cle]?.trim()).map((cle) => [cle, url]),
  );
}
