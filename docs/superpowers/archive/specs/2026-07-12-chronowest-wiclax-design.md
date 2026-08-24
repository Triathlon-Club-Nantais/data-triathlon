# Supporter `chronowest.fr` (déploiement Wiclax / G-Live)

**Date** : 2026-07-12
**Branche** : `worktree-spec-chronowest-wiclax`
**Issue** : [#35](https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/35)
(sous-issue de #33, section A — extensions de moteurs existants)
**Statut** : Design à valider

## Problème

`chronowest.fr` n'est pas un nouveau moteur de chronométrage : c'est un
**déploiement Wiclax / G-Live** (déjà supporté) sous un autre nom de domaine. La
page de résultats est une coquille WordPress de ~600 octets contenant une seule
`<iframe>` vers le moteur G-Live, lui-même alimenté par un fichier `.clax` (XML)
qui contient toute l'épreuve.

Aujourd'hui, une URL `chronowest.fr` n'est reconnue par aucun provider du
registre → elle tombe sur le fallback `playwright`, qui refuse l'import
d'épreuve. Résultat : les courses chronométrées par ChronoWest sont
inaccessibles à l'app.

## Constat de terrain (vérifié le 2026-07-12)

Le point important — et il réduit fortement le périmètre — c'est que **le moteur
Wiclax existant parse déjà chronowest de bout en bout**. Vérifié en appelant
directement `wiclax.scrape_event_all()` (en contournant le registre) :

| Épreuve | Participants parsés | Finishers | `event_type` | Date |
|---|---|---|---|---|
| `trail-des-2-ponts-2026` | 415 | 323 | `trail` | 2026-06-28 |
| `red-ouf-2026` (RED OUF Swimrun) | 162 | 149 | `swimrun` | 2026-06-28 |
| `locorrida-2026` | ❌ `404` | — | — | — |

Le `.clax` de ChronoWest a exactement la même structure que celui de
ChronoSmetron (racine `<Epreuve>`, concurrents dans `<Engages><E d=…>`, temps
dans `<Resultats><R d=…>`, bloc `<Segments>`). Les dossards, splits, statuts
(DNS/DNF) et les rangs calculés au tri sortent corrects sans toucher au parseur.

Il reste donc **trois** points de blocage, tous dans la résolution d'URL :

### 1. L'host n'est pas reconnu (cause du fallback playwright)

`WiclaxProvider.matches()` (`app/scrapers/registry.py:94`) ne connaît que
`wiclax-results.com`, `chronosmetron.com` et `wiclax.com`.

### 2. L'extraction de l'`<iframe>` se casse sur une apostrophe

`wiclax._resolve_to_wiclax_url()` (`app/scrapers/wiclax.py:172`) extrait le `src`
avec la regex :

```python
r'<iframe[^>]+src=["\']([^"\']+g-live\.html[^"\']*)["\']'
```

La classe `[^"\']` **s'arrête à la première apostrophe**. Or les noms d'épreuves
français en contiennent : le fichier de la Loc'Orrida s'appelle
`LOC'orrida 2026.clax`. Le `src` capturé est tronqué à
`…/glive-results/locorrida-2026/LOC` → `404`. C'est la cause exacte de l'échec
ci-dessus, et elle frappera n'importe quel host (y compris ceux déjà supportés).

### 3. Le répertoire `/G-Live/` est codé en dur

`wiclax._fetch_clax()` (`app/scrapers/wiclax.py:201`) résout le paramètre `f=`
contre un chemin figé :

```python
glive_dir = "/G-Live/"
clax_url = urljoin(base + glive_dir, f_param)
```

Chez ChronoWest, le moteur vit sous `/wp-content/glive/g-live.html` et le `f=`
est racine-absolu (`/wp-content/glive-results/…`). Ça fonctionne aujourd'hui *par
accident* — un chemin racine-absolu écrase la base dans `urljoin`. Dès qu'un
déploiement WordPress utilisera un `f=` relatif (`../`, comme le fait
ChronoSmetron), la résolution partira sur `/G-Live/` et échouera.

## Objectif

Reconnaître `chronowest.fr` et **généraliser** la chaîne de résolution
« page → iframe G-Live → `.clax` » pour qu'elle soit indépendante de l'hébergeur,
sans toucher au parseur `.clax` (aucun changement de comportement attendu sur les
providers existants).

## Architecture

Trois changements, tous dans `backend/app/scrapers/`.

### A. `registry.py` — reconnaître l'host

Ajouter `chronowest.fr` à la liste d'hosts de `WiclaxProvider.matches()`.

Le choix reste une **allowlist explicite d'hosts**, pas du sniffing de contenu :
détecter « c'est du G-Live » exigerait de télécharger la page de n'importe quelle
URL inconnue avant de savoir la traiter. Le fallback `playwright` continue de
capter le reste. Chaque nouveau déploiement Wiclax tiers = une ligne ici.

### B. `wiclax.py` — extraire l'iframe avec un parseur HTML

Remplacer la regex par **BeautifulSoup** (déjà une dépendance du projet, utilisée
par les autres scrapers) :

```python
soup = BeautifulSoup(resp.text, "lxml")
for ifr in soup.find_all("iframe"):
    src = ifr.get("src") or ""
    if "g-live.html" in src.lower():
        return urljoin(url, src)
```

Trois bénéfices par rapport à la regex : les apostrophes dans l'attribut ne
tronquent plus rien (bug #2), les entités HTML (`&amp;`) sont déjà décodées, et
le `src` est résolu contre **l'URL de la page** (`urljoin(url, src)`) — correct
pour un `src` absolu (ChronoWest : `https://chronowest.fr/wp-content/glive/…`)
comme racine-relatif (ChronoSmetron : `/G-Live/g-live.html?f=…`).

La même troncature guette la regex `href=…wiclax-results\.com…` de la branche
`chronosmetron.com` (`wiclax.py:161`) : la basculer sur BeautifulSoup aussi.

### C. `wiclax.py` — résoudre `f=` relativement au `g-live.html`

Supprimer le `/G-Live/` en dur et résoudre contre l'URL réelle du moteur :

```python
clax_url = urljoin(url, f_param)   # url = …/g-live.html?f=…
```

Vérifié sur les deux familles (résolution + `GET` du `.clax`) :

| Déploiement | `g-live.html` | `f=` | `.clax` résolu |
|---|---|---|---|
| ChronoSmetron | `/G-Live/g-live.html` | `../Triathlon de la Roche 2026/…clax` | `200` (855 Ko) |
| ChronoWest | `/wp-content/glive/g-live.html` | `/wp-content/glive-results/…clax` | `200` (108 Ko) |
| ChronoWest (apostrophe) | idem | `…/LOC'orrida 2026.clax` | `200` (89 Ko) |

C'est **strictement plus général** que le code actuel et ça préserve le résultat
sur ChronoSmetron (non-régression vérifiée).

### D. (recommandé) Suivre le lien depuis la page épreuve

ChronoWest expose deux formes d'URL, et un membre du club peut coller l'une ou
l'autre :

- `https://chronowest.fr/resultats/<slug>/` — la coquille à `<iframe>` ;
- `https://chronowest.fr/<slug>/` — la page épreuve WordPress, qui **ne contient
  pas** l'iframe mais un lien `href` vers la première.

`_resolve_to_wiclax_url` est déjà récursive (elle l'est pour `chronosmetron.com`).
Étendre le repli : si aucune `<iframe>` G-Live n'est trouvée, chercher un lien
vers `/resultats/…` sur la page et **recurser une fois** (garde anti-boucle :
profondeur max 2, puis `ValueError` avec un message explicite).

### E. `event_type` : classer le nom qualifié, pas le parcours nu

Découvert à la planification. `_parse_competitor` écrasait l'`event_type` par
`classify_event_type(p)`. Le classifieur retombant sur `triathlon` par défaut
(`classify.py`, étape 4), les parcours ChronoWest qui ne nomment pas le sport
(« S Duo », « M Solo ») faisaient importer le **RED OUF Swimrun en triathlon-s**.

Correctif : classer le nom qualifié (« RED OUF Swimrun 2026 - S Duo ») → sport
depuis le nom d'épreuve, taille depuis le parcours. Vérifié sans aucun changement
sur ChronoSmetron (Relais S/M/L, 6-9 Ans → types identiques).

## Flux

```
URL collée (une des trois formes)
  │
  ├─ chronowest.fr/<slug>/            ──href──▶ chronowest.fr/resultats/<slug>/   (D)
  │
  ├─ chronowest.fr/resultats/<slug>/  ──iframe──▶ /wp-content/glive/g-live.html?f=… (B)
  │
  └─ …/g-live.html?f=…                                                              │
                                                                                    ▼
                                          urljoin(url_g-live, f=)  ──▶  <Epreuve>.clax  (C)
                                                                                    │
                              parseur .clax existant, inchangé  ◀──────────────────┘
                              (<Engages><E>, <Resultats><R>, <Segments>)
```

## Tests

**Unitaires (sans réseau)** — dans `backend/tests/test_wiclax.py` :

1. `matches()` — `chronowest.fr` → provider `wiclax` (et non `playwright`) ;
   non-régression sur les hosts déjà supportés.
2. **Extraction d'iframe** — fixture HTML de la coquille ChronoWest (le vrai
   fichier fait ~600 octets, à committer dans `tests/fixtures/`), dont **un cas
   avec apostrophe** (`LOC'orrida 2026.clax`) : le `src` extrait doit être
   complet. C'est le test de non-régression du bug #2.
3. **Résolution du `.clax`** — table des trois combinaisons
   (`g-live.html` sous `/G-Live/` + `f=` relatif `../` ; `g-live.html` sous
   `/wp-content/glive/` + `f=` racine-absolu) → URL attendue. Test de C.
4. **Parsing** — fixture `.clax` **réduite** (quelques `<E>`/`<R>` + un
   `<Segments>`, extraite d'une épreuve ChronoWest réelle) → dossards, temps,
   splits, DNS/DNF, rangs. Confirme que le format est bien le même.

**Intégration (réseau réel, marker `integration`)** — dans
`backend/tests/test_integration_scrapers.py`, ajouter une entrée ChronoWest à
côté de l'entrée `wiclax` existante. Choisir une épreuve **terminée et stable** :
`https://chronowest.fr/resultats/trail-des-2-ponts-2026/` (415 participants).

> ⚠️ Ne **pas** prendre l'URL d'exemple de l'issue
> (`/resultats/armorun-2025/`) : son `.clax` a été réinitialisé pour l'édition
> 2026 (dt1 = 2026-08-22, pas encore courue) et ne contient plus ni `<Engages>`
> ni `<Resultats>` — 0 résultat. Ce n'est pas un bug de scraper, c'est le fichier
> source qui est vide.

## Hors périmètre (YAGNI / risques assumés)

- **Ne pas** lire le nom d'épreuve depuis l'attribut `nom=` de `<Epreuve>`. Le
  code prend aujourd'hui le nom du fichier `.clax` ; basculer sur `nom=`
  changerait le nom des Courses ChronoSmetron déjà en base
  (« Triathlon de la Roche » → « Triathlon de la Roche 2026 ») et créerait des
  doublons (`UNIQUE(name, event_date, event_type)`).
- **Ne pas** restreindre `root.iter("E")` / `root.iter("R")` aux blocs
  `<Engages>` / `<Resultats>`. L'itération large ramasse aussi `Equipes/E`,
  `Editions/E` et `AttribDosReels/R` — vérifié : **aucun** ne porte l'attribut
  `d`, donc aucun ne pollue les résultats (0 collision de clé sur l'épreuve
  ChronoSmetron de référence). Scoper serait plus propre mais risquerait de
  casser des `.clax` anciens sans ces conteneurs, pour un gain nul aujourd'hui.
- **Détection automatique** d'un déploiement G-Live sur un host inconnu : non.
  Allowlist explicite (voir A).
- **Équipes / relais** : les épreuves en équipe (RED OUF Swimrun) sortent avec un
  nom d'équipe et un prénom `.`. Comportement Wiclax préexistant, non aggravé par
  ce changement.

## Effort

**S** — trois modifications localisées, aucun changement du parseur `.clax`. Le
gros du travail est en tests (fixtures + non-régression sur les hosts existants).
