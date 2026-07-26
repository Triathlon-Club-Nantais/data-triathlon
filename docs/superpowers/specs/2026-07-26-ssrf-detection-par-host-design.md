# SSRF : détection de provider par host et validation d'URL — design

Issue [#49](https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/49).
Origine : suggestion de @MathieuHerrmann en approuvant la PR #36.

## Le trou

`app/schemas/scrape.py` déclare `url: str`, sans validation, et cinq providers de
`scrapers/registry.py` détectent l'URL par **sous-chaîne sur l'URL entière**,
pas sur le host :

| Ligne | Provider | Prédicat |
| --- | --- | --- |
| `registry.py:53` | klikego | `"klikego.com" in url` |
| `registry.py:78` | breizhchrono | `"breizhchrono.com" in url.lower()` |
| `registry.py:128` | timepulse | `"timepulse.fr" in url` |
| `registry.py:138` | prolivesport | `"prolivesport.fr" in url` |
| `registry.py:148` | sportinnovation | `"sportinnovation.fr" in url` |

L'issue en recensait quatre : **klikego** s'y ajoute. Il ne passe pas l'URL brute
à son scraper — il en extrait `event_id` et reconstruit ses URLs — donc il ne
porte pas le SSRF ; il porte le défaut de **routage** (voir « Détection » plus bas).
Les quatre autres transmettent l'URL telle quelle.

Conséquence, depuis l'endpoint public :

```
POST /api/v1/scrape/event  {"url": "https://169.254.169.254/latest/meta-data/?x=timepulse.fr"}
```

La sous-chaîne est dans la query, `TimePulseProvider` matche, et la requête part
**depuis le serveur** vers l'host choisi par l'appelant. Réseau interne,
métadonnées d'instance, services non exposés. La réponse n'est pas restituée (le
parsing échoue), mais erreurs et latences suffisent au balayage.

Deux prédicats supplémentaires sont vulnérables sans être des sous-chaînes d'URL :

- `WiclaxProvider` (`registry.py:117`) — `host.endswith("wiclax.com")` sans point
  suit aussi `evilwiclax.com` ;
- `_validate_url` (`import_service.py:45`) — `url.startswith("http")` accepte
  `httpfoo://…` et ne vérifie aucun host.

## Ce qui n'est pas concerné

- **`PlaywrightProvider`**, fallback des URLs non reconnues, **lève avant toute
  requête réseau**. Le fallback générique est donc déjà fermé : le point 3 de
  l'issue (« whitelist explicite comme filet ») repose sur une prémisse fausse et
  ne fermerait rien qui soit ouvert. On ne l'implémente pas — voir
  « Décisions écartées ».
- **`GET /scrape/detect`** — `detect_provider` est du pur appariement de chaînes,
  aucune requête sortante. Il reste en `url: str`.
- **`app/scrapers/playwright_fallback.py`** — code mort, aucun import dans
  `app/` ni `tests/` (reliquat du scraping athlète-unique supprimé). C'est le
  seul module capable de naviguer vers une URL arbitraire, mais rien ne l'appelle.

## Correctif

### 1. Une seule définition de « ce host est le sien »

Une fonction libre dans `registry.py` — les neuf classes de provider y vivent
déjà, aucune frontière de module n'est franchie :

```python
def _host_match(url: str, hosts: tuple[str, ...]) -> bool:
    """Host exact ou vrai sous-domaine.

    `hostname` et non `netloc` : sans lui, un port explicite
    (`my.raceresult.com:443`) ou des credentials feraient rater le match.
    Le point compte — `endswith` nu suivrait aussi `evil-timepulse.fr`.
    """
    host = (urlparse(url).hostname or "").lower()
    return any(host == h or host.endswith(f".{h}") for h in hosts)
```

Et une classe de base qui en fait le **défaut** :

```python
class HostMatchedProvider:
    """Détection par host. Défaut de tout provider : il n'y a pas de `matches`
    à écrire, donc pas de `in url` à réintroduire par mégarde (cf. #76)."""

    _HOSTS: tuple[str, ...] = ()

    def matches(self, url: str) -> bool:
        return _host_match(url, self._HOSTS)
```

Sept providers sur huit se réduisent à `name` + `_HOSTS` + `scrape_event_all`.
`RaceResultProvider` et `ChronoplaceProvider`, qui portaient déjà chacun leur
copie correcte de la règle, rejoignent la définition commune.

**Wiclax est le cas qui décide de la forme.** `wiclax.com` est délibérément hors
de `_HOSTS` — c'est le site vitrine de l'éditeur, seuls les chemins G‑Live sont
des pages de résultats. Il lui faut donc la règle comme *expression*, pas comme
méthode héritée :

```python
def matches(self, url: str) -> bool:
    return super().matches(url) or (
        _host_match(url, ("wiclax.com",)) and "G-Live" in (urlparse(url).path or "")
    )
```

C'est pourquoi la fonction libre **et** la classe de base : une classe de base
seule obligerait Wiclax à recopier la règle, c'est-à-dire à rouvrir exactement la
duplication qu'elle vient fermer.

### 2. Validation d'entrée, à deux niveaux

`ScrapeRequest` ne couvre que deux des chemins d'import. Les deux niveaux sont
donc nécessaires, et ne font pas doublon :

- **`ScrapeRequest.url: HttpUrl`** — rejet en 422 dès la porte pour
  `POST /scrape/event` et `/scrape/event/stream`. Les routers passent
  `str(body.url)` au service.
- **`import_service._validate_url` durci** — `urlparse` exigeant
  `scheme in {"http", "https"}` **et** un host non vide, sinon `InvalidUrlError`
  (400). C'est le passage obligé de **tous** les chemins d'import (API, SSE, CLI
  `import-sheet`, CLI `rescrape-db`) et donc la seule garde du batch, qui n'a
  aucun schéma Pydantic.

`HttpUrl` a été mesuré sur pydantic 2.13.4, pas seulement retenu sur documentation :
il **normalise**, il ne se contente pas de valider. Sur nos URLs réelles, trois
réécritures constatées : le port par défaut est supprimé (`my.raceresult.com:443`
devient `my.raceresult.com`, cas réel — cette URL est dans `_ROUTAGE_LEGITIME` de
`test_registry.py`), les espaces et caractères non-ASCII du chemin sont
percent-encodés, et une URL de plus de 2083 caractères est rejetée en 422
(`url_too_long`, limite non documentée par ailleurs). Il rejette aussi `file://`,
`gopher://`, `ftp://`, `javascript:`.

La dérive de clé de cache (`source_url`) qu'on pouvait craindre a donc bien lieu
sur les URLs concernées — mais sa conséquence reste bornée :
`course_repository.get_or_create` apparie par identité (`name`, `event_date`,
`event_type`, `is_relay`), pas par `source_url`, donc **aucun doublon de course
n'est créé**. En revanche `get_latest_by_source_url` rate le rapprochement, et
`get_or_create` ne réécrivant pas le `source_url` d'une ligne existante, le
cache TTL reste durablement inefficace pour ces URLs (re-scrape à chaque
import). Assumé : la normalisation ferme le SSRF, ce coût résiduel est un
compromis, pas un oubli.

Il ne rejette **pas** `http://169.254.169.254/…` : c'est le point 1 qui ferme ce
chemin, en refusant de router une IP littérale vers un provider.

### 3. Tests de non-régression

Sur les huit providers, quatre familles de contournement :

- sous-chaîne en query — `https://169.254.169.254/?x=timepulse.fr` ;
- sous-chaîne en path — `https://evil.example/timepulse.fr/` ;
- host sosie sans point — `https://evil-timepulse.fr/` (et `evilwiclax.com`) ;
- sous-domaine légitime — `https://www.timepulse.fr/…` doit **continuer** à matcher.

Plus :

- un host inconnu tombe sur `playwright` et **ne déclenche aucune requête** —
  c'est ce test qui tient lieu du point 3 (voir ci-dessous) ;
- la non-régression de détection notée par l'issue : une URL Klikego portant
  `timepulse.fr` en paramètre part chez Klikego ;
- schéma non-http rejeté en 422 par l'API, et en `InvalidUrlError` par le service.

## Détection, hors sécurité

Le point 1 corrige aussi un défaut de **routage** : aujourd'hui, une URL Klikego
contenant `timepulse.fr` en paramètre part chez le mauvais scraper. C'est le seul
effet du correctif visible sur des URLs légitimes.

## Décisions écartées

**Whitelist explicite avant scrape (point 3 de l'issue).** Écartée : le refus
existe déjà, par `PlaywrightProvider` qui lève. Un second contrôle créerait une
deuxième définition de « host supporté » à côté de `PROVIDERS`, avec le risque de
divergence que #76 a déjà coûté en production. On verrouille le comportement
existant par un test explicite plutôt que de le dupliquer.

**Classe de base seule, sans fonction libre.** Écartée : ne couvre pas Wiclax
sans recopier la règle (voir §1).

**Fonction libre seule, sans classe de base.** Écartée : le correctif protégerait
aujourd'hui sans protéger demain — rien n'empêcherait l'auteur du prochain
provider d'écrire `return "foo.fr" in url`. Avec la classe de base, il n'y a plus
de `matches` à écrire.

## Résidu connu, hors périmètre

**SSRF par redirection.** Les huit scrapers, `sheet_source` et l'auto-détection
de heat de `registry.py` sont en `follow_redirects=True` — 13 sites d'appel sur
10 modules. Une fois le point 1 en place, l'appelant public ne
choisit plus l'host ; mais un host provider qui répondrait `302 →
http://169.254.169.254/` ferait toujours partir la requête. L'exploiter suppose
de contrôler un host provider — compromission ou prise de sous-domaine — ce qui
n'est plus à la portée de l'endpoint public.

Le couvrir demanderait de revalider le host à chaque saut (`follow_redirects=False`
+ boucle, ou hook httpx d'événement) sur tous ces sites, avec un risque de
régression sur des redirections légitimes (`www` → apex, `http` → `https`) que le
panel de tests d'intégration ne couvre pas entièrement. Ticket de suivi à ouvrir.

**`playwright_fallback.py`, code mort.** Sa suppression est un nettoyage
souhaitable — tant qu'il existe, un futur appelant peut le rebrancher sans voir
qu'il navigue vers une URL arbitraire — mais elle n'appartient pas à ce
correctif. Ticket de suivi à ouvrir.
