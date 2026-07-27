// @vitest-environment node
import { describe, expect, it, afterEach } from "vitest";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { join } from "node:path";

import {
  DEFAULT_BACKEND_URL,
  PORT_FILE_NAME,
  isPortAlive,
  missingBackendEnv,
  readPublishedBackend,
  resolveBackendUrl,
} from "./backend-url.mjs";

const aNettoyer = [];

afterEach(async () => {
  await Promise.all(aNettoyer.splice(0).map((fn) => fn()));
});

/** Crée un répertoire temporaire jouant le rôle de racine de worktree. */
async function racineTemporaire() {
  const dir = await mkdtemp(join(tmpdir(), "dev-backend-"));
  aNettoyer.push(() => rm(dir, { recursive: true, force: true }));
  return dir;
}

/** Démarre un vrai serveur TCP et rend son port — pas de simulation de socket. */
async function serveurEcoutant() {
  const server = createServer();
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  aNettoyer.push(() => new Promise((resolve) => server.close(resolve)));
  return server.address().port;
}

/** Un port qu'un serveur a occupé puis libéré : personne n'écoute plus. */
async function portMort() {
  const server = createServer();
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const { port } = server.address();
  await new Promise((resolve) => server.close(resolve));
  return port;
}

async function publier(root, port) {
  await writeFile(
    join(root, PORT_FILE_NAME),
    JSON.stringify({ port, url: `http://127.0.0.1:${port}`, pid: 4242 }),
    "utf-8",
  );
}

describe("readPublishedBackend", () => {
  it("rend null quand aucun backend n'a publié son port", async () => {
    expect(await readPublishedBackend(await racineTemporaire())).toBeNull();
  });

  it("rend null sur un fichier corrompu plutôt que de jeter", async () => {
    const root = await racineTemporaire();
    await writeFile(join(root, PORT_FILE_NAME), "{ pas du json", "utf-8");

    expect(await readPublishedBackend(root)).toBeNull();
  });

  it("rend le port et l'URL publiés", async () => {
    const root = await racineTemporaire();
    await publier(root, 8042);

    expect(await readPublishedBackend(root)).toMatchObject({
      port: 8042,
      url: "http://127.0.0.1:8042",
    });
  });
});

describe("DEFAULT_BACKEND_URL", () => {
  it("vise le loopback et non l'adresse d'écoute du backend", () => {
    // Le backend écoute `0.0.0.0` (conteneurs), mais cette URL est une **destination** :
    // `0.0.0.0` n'en désigne aucune, et seul Linux la tolère en connexion sortante.
    expect(DEFAULT_BACKEND_URL).toBe("http://127.0.0.1:8001");
  });
});

describe("isPortAlive", () => {
  it("répond vrai quand un serveur écoute", async () => {
    expect(await isPortAlive(await serveurEcoutant())).toBe(true);
  });

  it("répond faux sur un port que plus personne n'écoute", async () => {
    expect(await isPortAlive(await portMort())).toBe(false);
  });
});

describe("resolveBackendUrl", () => {
  it("respecte BACKEND_URL sans rien attendre", async () => {
    const resultat = await resolveBackendUrl({
      env: { BACKEND_URL: "http://backend.example:9999" },
      root: await racineTemporaire(),
      timeoutMs: 0,
    });

    expect(resultat).toEqual({ url: "http://backend.example:9999", source: "env" });
  });

  it("retient le port publié quand le backend répond", async () => {
    const root = await racineTemporaire();
    const port = await serveurEcoutant();
    await publier(root, port);

    const resultat = await resolveBackendUrl({ env: {}, root, timeoutMs: 1000 });

    expect(resultat).toEqual({ url: `http://127.0.0.1:${port}`, source: "file" });
  });

  it("se rabat sur le port par défaut quand rien n'est publié", async () => {
    const resultat = await resolveBackendUrl({
      env: {},
      root: await racineTemporaire(),
      timeoutMs: 60,
      pollMs: 10,
    });

    expect(resultat).toEqual({ url: DEFAULT_BACKEND_URL, source: "fallback" });
  });

  it("ignore un fichier périmé dont le port ne répond plus", async () => {
    // Backend tué par kill -9 : le fichier survit, mais le suivre proxyfierait dans le vide.
    const root = await racineTemporaire();
    await publier(root, await portMort());

    const resultat = await resolveBackendUrl({ env: {}, root, timeoutMs: 60, pollMs: 10 });

    expect(resultat.source).toBe("fallback");
  });

  it("attend un backend démarré après le front", async () => {
    const root = await racineTemporaire();
    const port = await serveurEcoutant();
    setTimeout(() => void publier(root, port), 40);

    const resultat = await resolveBackendUrl({ env: {}, root, timeoutMs: 2000, pollMs: 10 });

    expect(resultat).toEqual({ url: `http://127.0.0.1:${port}`, source: "file" });
  });

  it("signale l'attente une seule fois", async () => {
    const appels = [];
    await resolveBackendUrl({
      env: {},
      root: await racineTemporaire(),
      timeoutMs: 60,
      pollMs: 10,
      onWait: () => appels.push(1),
    });

    expect(appels).toHaveLength(1);
  });
});

describe("missingBackendEnv", () => {
  it("renseigne les deux variables quand l'environnement est vide", () => {
    expect(missingBackendEnv({}, "http://127.0.0.1:8042")).toEqual({
      BACKEND_URL: "http://127.0.0.1:8042",
      API_URL: "http://127.0.0.1:8042",
    });
  });

  it("laisse intacte une API_URL fournie et ne comble que BACKEND_URL", () => {
    // Dissocier la cible SSR de celle des rewrites doit rester possible.
    expect(missingBackendEnv({ API_URL: "http://autre:9000" }, "http://127.0.0.1:8042")).toEqual({
      BACKEND_URL: "http://127.0.0.1:8042",
    });
  });

  it("n'injecte rien quand les deux variables sont déjà définies", () => {
    const env = { BACKEND_URL: "http://a:1", API_URL: "http://b:2" };

    expect(missingBackendEnv(env, "http://127.0.0.1:8042")).toEqual({});
  });

  it("traite une valeur vide ou blanche comme absente", () => {
    expect(missingBackendEnv({ BACKEND_URL: "", API_URL: "   " }, "http://127.0.0.1:8042")).toEqual({
      BACKEND_URL: "http://127.0.0.1:8042",
      API_URL: "http://127.0.0.1:8042",
    });
  });
});
