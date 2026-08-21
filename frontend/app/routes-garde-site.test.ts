import { readdirSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Placement des routes vis-à-vis de la garde d'accès au site (#509).
 *
 * Un test de **structure de dossiers**, et non de rendu : le piège que couvre
 * cette suite n'est pas un composant qui se trompe, c'est une route rangée du
 * mauvais côté de `app/(public_restricted)/` — une erreur invisible à la lecture d'un
 * fichier, et qui ferme le site à clé sans laisser la clé dedans.
 *
 * `login` en est le cas limite, relevé en revue de #513 : sur un déploiement
 * neuf (`site_access_config` vide), `require_site_access` est fail-closed, donc
 * la garde renvoie tout le groupe vers `/acces` — où aucun mot de passe
 * n'existe encore. Le seul chemin de sortie est le SSO d'un administrateur vers
 * `/admin/acces`, et il passe par `/login`. Rangé sous le groupe, ce chemin se
 * referme sur lui-même : `/admin` → `/login` → `/acces` → impasse.
 */
const APP = join(__dirname);
const GROUPE_RESTREINT = join(APP, "(public_restricted)");

function dossiers(chemin: string): string[] {
  return readdirSync(chemin, { withFileTypes: true })
    .filter((entree) => entree.isDirectory())
    .map((entree) => entree.name);
}

describe("Placement des routes vis-à-vis de la garde d'accès au site (#509)", () => {
  const racine = dossiers(APP);
  const restreintes = dossiers(GROUPE_RESTREINT);

  // `login` : sans lui, plus aucun administrateur ne peut se connecter sur un
  // déploiement neuf. `acces` : la cible de la garde. `benevoles` : population
  // potentiellement non-adhérente (#271). `admin` : pose le premier mot de passe.
  it.each(["login", "acces", "benevoles", "admin"])(
    "`%s` reste une route sœur, hors du groupe gardé",
    (route) => {
      expect(racine).toContain(route);
      expect(restreintes).not.toContain(route);
    },
  );

  it.each(["dashboard", "resultats", "athletes", "courses", "club", "carte", "ajouter"])(
    "`%s` vit sous le groupe gardé",
    (route) => {
      expect(restreintes).toContain(route);
    },
  );
});
