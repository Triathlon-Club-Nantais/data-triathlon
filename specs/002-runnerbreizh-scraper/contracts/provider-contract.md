# Contrat du provider `runnerbreizh`

Le module n'expose aucune interface HTTP ni CLI nouvelle. Son seul contrat est
`registry.ScraperProtocol`, et les invariants que les tests verrouillent.

## Interface

```python
class RunnerBreizhProvider(HostMatchedProvider):
    name = "runnerbreizh"
    _HOSTS = ("runnerbreizh.fr",)

    def scrape_event_all(self, url: str) -> list[ScrapedResult]: ...
```

`matches()` est **hérité** : le provider n'en écrit pas. Sa condition se réduit à
une liste de hosts, donc `HostMatchedProvider` suffit et la règle « host exact ou
vrai sous-domaine » reste définie une seule fois dans `registry._host_match`
(garde SSRF de #49).

Position dans `PROVIDERS` : indifférente — aucun autre provider ne revendique
`runnerbreizh.fr`. On l'ajoute avant `T2AreaProvider` pour garder le fallback
Playwright en dernier.

## Invariants vérifiés par les tests

### Détection

| Entrée | Attendu |
| --- | --- |
| `https://www.runnerbreizh.fr/requetetriathlons.php?CourseFichierGpsNom=…` | détecté `runnerbreizh` |
| `https://runnerbreizh.fr/requetetriathlons.php?…` (apex) | détecté `runnerbreizh` |
| `https://evil-runnerbreizh.fr/…` | **non** détecté (non-régression SSRF #49) |
| `https://exemple.fr/?x=runnerbreizh.fr` | **non** détecté (jeton en query) |
| `https://timepulse.fr@runnerbreizh.fr/…` | détecté sur le host réel, jamais sur les credentials |
| `https://[oops/x` | non-match, **sans exception** |

### Scraping

| Cas | Attendu |
| --- | --- |
| URL avec `&page=3` | import complet depuis la page 1 |
| URL avec `&Sexe=F` | import complet, filtre ignoré |
| URL avec `&tricourse=4` | import complet, tri ignoré |
| Dernière page partielle | toutes les lignes, pas de requête au delà de la première page vide |
| Page vide immédiate + titre valide | liste vide, **pas** d'exception |
| Titre vide + page vide | `ValueError` « épreuve introuvable » |
| `triathlons.php?CoureurNom=…` | `ValueError` nommant la forme d'URL attendue |
| Ligne à un nombre de cellules inattendu | ligne ignorée et journalisée, les autres importées |

### Contenu d'un `ScrapedResult`

| Invariant | Vérification |
| --- | --- |
| `source_url` du `ScrapedResult` est l'URL **canonique** | égalité stricte, quelle que soit la forme d'entrée. `Course.source_url`, lui, vient de l'`event_url` du service : voir research D2 |
| `provider == "runnerbreizh"` | sur toutes les lignes |
| `event_name` sans le suffixe `(0.75/20/5)` | égalité stricte |
| `distance_km` renseigné depuis le titre | `25.75` |
| Aucun `bib_number`, aucun `club` | chaîne vide sur toutes les lignes |
| Temps au format `HH:MM:SS` | `total_time` et segments |
| Aquathlon : pas de segment vélo | `bike_time == ""` |
| Duathlon : `build_splits` rend `course1`/`bike`/`course2` | test via `services.mapping` |
| Duo : deux lignes, même `rank_overall`, `is_relay` vrai | 2 résultats |
| Ligne anonyme : nom intégral, prénom vide | `athlete_name == "?DOSSARD #9998"` |
| `raw_data` porte rangs de segment, vitesses, total | clés présentes |

### Coût réseau

Le nombre d'appels HTTP est **compté** dans les tests (le client factice les
enregistre) : `pages + 1` pour une épreuve, et aucune requête par participant.
C'est la garde contre une régression du type « une requête par fiche »
(le coût assumé de T2Area, à ne pas reproduire ici où rien ne l'exige).

## Effets de bord sur les contrats existants

- `registry.provider_names()` gagne `runnerbreizh` → `--provider runnerbreizh` et
  `--only-provider runnerbreizh` deviennent valides sans modifier
  `cli/validators` (la liste est dérivée de `PROVIDERS`).
- `sheet_source.is_supported` reconnaît les liens runnerbreizh → ils quittent la
  catégorie `ignored_by_host` (#33) et entrent dans le batch, où ils comptent
  désormais en succès ou en échec.
- Aucun changement de réponse d'API : les DTO existants exposent déjà `is_tcn`
  (faux ici, faute de club) et `splits`.
