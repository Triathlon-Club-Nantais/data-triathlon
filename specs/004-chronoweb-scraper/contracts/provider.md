# Contrat d'interface — provider `chronoweb`

Le fournisseur n'expose aucune interface HTTP ni CLI propre : il s'insère dans
deux contrats déjà établis. Aucun contrat public existant n'est modifié
(principe IV : `/api/v1` et les sorties CLI restent inchangés).

## 1. Contrat de registre (`app/scrapers/registry.ScraperProtocol`)

```python
class ChronoWebProvider(HostMatchedProvider):
    name = "chronoweb"
    _HOSTS = ("chronoweb.com",)

    def scrape_event_all(self, url: str) -> list[ScrapedResult]: ...
```

| Élément | Engagement |
| --- | --- |
| `name` | `"chronoweb"` — apparaît dans `provider_names()`, donc ciblable par `--provider` / `--only-provider`, et rendu par `GET /scrape/detect`. |
| `matches` | **hérité** de `HostMatchedProvider` : host égal à `chronoweb.com` ou vrai sous-domaine. Aucune surcharge, aucun test de sous-chaîne sur l'URL (SSRF #49). |
| Position dans `PROVIDERS` | indifférente : aucun autre provider ne revendique ce host. Ajout en fin de liste, avant `T2AreaProvider`. |

**Effet de bord attendu** : `registry.is_supported("https://chronoweb.com/…")`
passe de `False` à `True`. Le front n'a rien à changer — il lit `is_supported`
depuis l'API et `PROVIDER_LABELS` traduit le slug (une entrée
`chronoweb: "ChronoWeb"` est à ajouter côté front pour l'affichage commercial,
son absence ne vaut pas « non supporté »).

## 2. Contrat de sortie (`app/scrapers/base.ScrapedResult`)

`scrape_event_all(url)` rend **une entrée par participant et par épreuve** de
l'événement désigné.

### Garanties

1. **Complétude** — toutes les épreuves de l'événement, tous les participants
   ayant franchi au moins un point.
2. **Unicité** — jamais deux entrées de même `(event_name, bib_number)`.
3. **Cardinalité des requêtes** — au plus 2 appels HTTP au site par invocation
   (le classement, puis le catalogue pour la commune).
4. **Temps** — chaînes `HH:MM:SS` normalisées ; `total_time` vide pour un
   non-finisher.
5. **Rangs** — `rank_overall` / `rank_category` renseignés **uniquement** pour
   qui a franchi le point final de l'épreuve ; `None` sinon. Aucun rang
   intermédiaire n'est promu en rang de classement (il reste dans
   `raw_data["points"]`) : il doublonnerait celui d'un finisher et ferait
   ressortir l'épreuve en `is_reliable=false`.
6. **Nom d'épreuve** — toujours non vide (sinon `import_service` refuse
   l'import) et qualifié du libellé d'épreuve.

### Erreurs

| Cas | Exception | Message (français, vu par l'opérateur) |
| --- | --- | --- |
| URL sans paramètre `event` | `ValueError` | nomme la forme attendue `resultats_evenement.php?event=<id>` |
| Identifiant d'événement inconnu | `ValueError` | « événement introuvable », distinct du cas suivant — le mot compte : une **épreuve** est l'unité de bilan de la CLI (une `source_url`), un **événement** en porte plusieurs |
| Événement sans classement publié | *aucune* | renvoie `[]` |

`import_service._scrape_all` convertit toute `ValueError` en
`ProviderNotSupportedError` et toute autre exception en `ScraperError` : les
deux apparaissent dans le détail des épreuves en erreur des bilans CLI.

## 3. Non-contrats (ce qui n'est pas promis)

- **Pas de club** : `club` vaut toujours `""`. Les participations sont hors du
  périmètre `scope=club`.
- **Pas de distinction DNS / DSQ** : un non-partant est invisible, un
  disqualifié ne se distingue pas d'un abandon.
- **Pas de rang de genre**.
- **Pas de stabilité de `Course.source_url`** : deux graphies d'URL du même
  événement produisent deux clés de cache (décidé en amont du fournisseur).
