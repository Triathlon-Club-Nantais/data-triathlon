# Scrapers

`registry.py` = le registre **Protocol** (fin des `if-else`) + un module par
provider ; `base.py` = le contrat partagé (`ScrapedResult`, `FanoutTrace`, les
constantes `STATUS_*`) ; `utils.py` = helpers de normalisation (dont
`DEFAULT_HEADERS`, `to_seconds`/`fmt_seconds`).

## Conventions


- Tout nouveau fournisseur : créer `scrapers/<nom>.py`, exposer
  `scrape_event_all()` — la **seule** voie d'import depuis la suppression du
  scraping athlète-unique —, puis l'enregistrer dans `scrapers/registry.py`
  (registre Protocol). Un provider **sans particularité** est une ligne
  `ModuleProvider("<nom>", ("<host>",), <module>)` dans `PROVIDERS`, pas une
  classe : seuls le fan-out, une double façade ou une règle de match composée
  en justifient une. Provider inconnu → `get_provider` rend `None` et le
  dispatcher lève : il n'y a **pas** de sentinelle attrape-tout, et un futur
  fallback générique se valide en amont sur une liste blanche de hosts, sans
  quoi il rouvrirait le SSRF de #49.
- **Détection par host, jamais par sous-chaîne d'URL.** Un provider déclare ses
  `_HOSTS` et hérite de `HostMatchedProvider` : il n'a pas de `matches` à
  écrire. La règle « host exact ou vrai sous-domaine » a une seule définition,
  `registry._host_match`. Un `"exemple.fr" in url` route n'importe quelle URL
  portant le jeton en query vers le scraper, qui la requête telle quelle —
  c'était le SSRF de #49. Un provider dont la condition ne se réduit pas à une
  liste de hosts (Wiclax : `wiclax.com` n'est une page de résultats que sur un
  chemin G-Live) surcharge `matches` et **compose** sur `_host_match`.
  Aucun `matches` n'appelle `urlparse` directement : le host se lit par
  `registry._url_host` (le path par `_url_path`), qui rendent `""` sur une URL
  illisible. `urlparse` lève sur un host IPv6 malformé (`https://[oops/x`), et
  `detect_provider` parcourt **tous** les providers : un seul `urlparse` nu —
  fût-il dans le dernier de la liste, T2Area — suffit à faire lever la
  détection entière, garde des autres comprise.
- **Toute sortie HTTP passe par `app/core/http.client()`**, jamais par
  `httpx.Client(...)` ni `httpx.get(...)` nus. La fabrique enveloppe le
  transport d'un garde qui refuse toute destination non publiquement routable
  (`not ip.is_global`), sur la requête initiale **et sur chaque saut de
  redirection** : #49 avait fermé le routage, un `302 → http://169.254.169.254/`
  restait ouvert (#101). Un méta-test refuse tout `httpx` nu dans `app/`. Deux
  conséquences à connaître : le refus lève `BlockedTargetError`, qui ne dérive
  pas de `ValueError` (sinon `import_service` la classerait en « fournisseur non
  supporté ») ; et une redirection vers un **autre domaine** reste autorisée —
  l'export CSV du Google Sheet en dépend. Design :
  `docs/superpowers/specs/2026-07-31-ssrf-redirection-design.md`.
- **Breizh Chrono réutilise la logique Klikego** (`klikego._parse_detail`) — ne
  pas dupliquer, factoriser dans `klikego.py`. Le type d'épreuve, lui, vient de
  `classify.classify_event_type`, appelé directement par chaque scraper.
- « Supporté ou non » : **une seule définition**, `registry.is_supported` (dérivée
  de `PROVIDERS`), exposée par `GET /scrape/detect` (`{provider, supported}`). Le
  front ne liste **jamais** les providers : la liste en dur qu'il portait est
  restée figée à six noms et affichait « Non supporté (competitor) » sur une URL
  ironman.com pourtant importable — RaceResult et Chronoplace étaient logés à la
  même enseigne. `lib/constants.PROVIDER_LABELS` ne fait que traduire un slug en
  nom commercial ; un slug absent s'affiche tel quel, sans jamais valoir « non
  supporté ».
- Identification club : **une seule définition**, `app/core/club.py`
  (`is_tcn` / `tcn_clause`). Ne jamais la réimplémenter ailleurs — front et
  scraper l'avaient fait, les trois listes ont divergé et tout libellé contenant
  « nantais » a été compté comme TCN (#76). Le front lit le champ `is_tcn` du DTO.
- Les temps restent des **strings** (`"01:23:45"`), normalisés via `utils.py`.
  Splits adaptés au sport : dans `splits` (JSON) + `raw_data` (JSON).

## Fournisseurs supportés

Tous en **épreuve complète** (`scrape_event_all()`). Les pièges mesurés, les
vérités d'API et les formes d'URL acceptées vivent dans un fichier par
fournisseur — à lire **avant** de toucher au module correspondant.

| Fournisseur | En bref | Détail |
| --- | --- | --- |
| Klikego, Breizh Chrono | Breizh Chrono **réutilise** `klikego._parse_detail` — factoriser dans `klikego.py`, ne jamais dupliquer. | — |
| TimePulse, ProLiveSport, Sportinnovation | rien au-delà des conventions ci-dessus. | — |
| Chronoplace | Laravel + Livewire, lu en `GET ?perPage=all` — pas de POST Livewire — et importe **toutes** les épreuves de l'événement pointé par l'URL. | — |
| Wiclax/G-Live | plusieurs déploiements : `wiclax-results.com`, `chronosmetron.com`, `chronowest.fr` (WordPress + iframe G-Live). Un déploiement tiers de plus = un host dans `WiclaxProvider._HOSTS`. | — |
| RaceResult | trois façades d'un même produit, une API JSON publique, listes `hidden` qui enrichissent par dossard (#60). | `docs/scrapers/raceresult.md` |
| T2Area (FFTRI) | Joomla server-rendered, une requête pour le classement ; splits sur la fiche individuelle, donc **seuls les membres du TCN** sont chargés. | `docs/scrapers/t2area.md` |
| Competitor | le moteur derrière `ironman.com` : page → uuid → JSON de proxy. Une URL désigne une **série**, pas une édition ; aucun club publié. | `docs/scrapers/competitor.md` |
| ok-time | API JSON WordPress publique, **un seul appel** pour l'événement entier ; points de passage cumulés, libellés rendus verbatim. | `docs/scrapers/oktime.md` |
| runnerbreizh | HTML statique paginé (50 lignes/page) ; ni dossard, ni club, ni date de naissance ; URL canonicalisée par allowlist. | `docs/scrapers/runnerbreizh.md` |
| Sporthive (MYLAPS) | API JSON publique sur `eventresults-api.speedhive.com` ; `size` plafonné à 10, statut dans `validity`, une course incomplète est écartée sans perdre l'événement. | `docs/scrapers/sporthive.md` |
| chronoweb | HTML statique, une requête pour l'événement entier ; une ligne = un **passage**, pas un participant. | `docs/scrapers/chronoweb.md` |

Types d'épreuve : Triathlon XS/S/M/L/XL, Duathlon XS/S/M/L, SwimRun S/M/L,
Aquathlon, Aquarun, Bike & Run.
