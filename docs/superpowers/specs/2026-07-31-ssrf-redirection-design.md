# SSRF par redirection : garde de destination sur tout le sortant HTTP — design

Issue [#101](https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/101).
Suite de [#49](https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/49)
(PR #100), dont le design nommait ce résidu en « Résidu connu, hors périmètre ».
Design de #49 : `docs/superpowers/specs/2026-07-26-ssrf-detection-par-host-design.md`.

## Le trou

#49 a fermé le **routage** : une URL dont le host n'est servi par aucun provider
tombe sur `PlaywrightProvider`, qui lève avant toute requête. Mais une fois le
host reconnu, la requête part en `follow_redirects=True`, et httpx suit la
redirection **sans revalider la cible**. Un host fournisseur qui répondrait
`302 → http://169.254.169.254/latest/meta-data/` ferait toujours partir la
requête vers l'adresse interne.

Gravité nettement moindre que #49 : exploiter ce vecteur suppose de **contrôler
un host fournisseur** — compromission d'un chronométreur, ou prise d'un
sous-domaine expiré. L'endpoint public ne choisit plus la cible.

### Le périmètre réel a bougé

Le ticket recense 13 sites sur 10 modules. Le décompte d'aujourd'hui est de
**17 sites `follow_redirects=True` sur 14 modules** — les scrapers ajoutés
depuis la rédaction (`t2area`, `runnerbreizh`, `competitor`, `oktime`) —, plus
`geocode_service`, seul `httpx.get` restant. Soit **18 sites de construction sur
15 modules**.

Sur les 50 occurrences de `httpx.Client` dans `app/`, **seules 18 sont des
constructions** : les 32 autres sont des annotations de paramètre (`client:
httpx.Client`) de fonctions qui reçoivent leur client. `klikego_platform.py` en
est entièrement fait, il n'a aucun site à migrer.

| Module | Sites | Forme |
| --- | --- | --- |
| `app/scrapers/breizhchrono.py` | 217, 384 | `httpx.Client` |
| `app/scrapers/sportinnovation.py` | 486, 627 | `httpx.Client` |
| `app/scrapers/timepulse.py` | 78, 92 | **`httpx.get`** |
| `app/scrapers/klikego.py` | 313 | `httpx.Client` |
| `app/scrapers/wiclax.py` | 273 | `httpx.Client` |
| `app/scrapers/prolivesport.py` | 237 | `httpx.Client` |
| `app/scrapers/raceresult.py` | 1351 | `httpx.Client` |
| `app/scrapers/chronoplace.py` | 467 | `httpx.Client` |
| `app/scrapers/t2area.py` | 515 | `httpx.Client` |
| `app/scrapers/runnerbreizh.py` | 501 | `httpx.Client` |
| `app/scrapers/competitor.py` | 361 | `httpx.Client` |
| `app/scrapers/oktime.py` | 671 | `httpx.Client` |
| `app/scrapers/registry.py` | 143 | `httpx.Client` (auto-détection de heat Klikego) |
| `app/services/sheet_source.py` | 87 | `httpx.Client` (Google Sheet du club) |
| `app/services/geocode_service.py` | 47 | **`httpx.get`**, sans redirections |

`httpx.get` n'accepte **ni** `transport` **ni** `event_hooks` (signature vérifiée
sur httpx 0.28.1) : ces trois sites passent en `Client` quelle que soit la piste
retenue.

## Mécanisme : transport, pas hook

Les deux mécanismes de la piste 1 du ticket ont été sondés sur `MockTransport`
(script jetable, non versionné). Ils fonctionnent tous les deux — mais pas
également.

| | `event_hook` sur `response` | transport enveloppant |
| --- | --- | --- |
| voit chaque saut | oui | oui |
| voit la requête **initiale** | non (elle n'est pas une 3xx) | oui |
| forme de la cible | `Location` **brut**, y compris relatif (`//169.254.169.254/meta`) | `request.url`, déjà résolue par httpx |
| bloque effectivement | oui | oui |

Le hook oblige à réimplémenter la résolution d'URL relative que httpx fait déjà,
pour une couverture strictement moindre. **Le transport est retenu.**

Vérifié sur le sondage : quand le garde lève au premier saut, le transport
interne ne voit **jamais** la seconde URL — la requête ne part pas.

## Le correctif

### 1. Un module, `app/core/http.py`

`app/core/` parce que le garde traverse les deux couches concernées : `scrapers/`
(16 sites) et `services/` (2 sites). Trois symboles :

```python
def client(**kwargs) -> httpx.Client        # la fabrique
class _GuardTransport(httpx.BaseTransport)  # privé
```

`BlockedTargetError` vit avec la famille, dans `app/core/exceptions.py`, et non
dans `core/http.py` : c'est là que sont toutes les `DomainError` et le
`register_exception_handlers` qui les sert. Une seconde maison pour les erreurs
métier serait exactement la duplication de définition que #76 a coûtée.

La fabrique pose `follow_redirects=True` par défaut et **enveloppe** le
transport :

```python
transport=_GuardTransport(kwargs.pop("transport", None) or httpx.HTTPTransport())
```

Composition, et non héritage de `HTTPTransport` : c'est ce qui rend le garde
testable sans réseau, en lui passant un `MockTransport` comme transport interne.

Elle appelle `httpx.Client(...)` par **résolution d'attribut sur le module
`httpx`**, jamais via un `from httpx import Client`. Ce détail n'est pas
cosmétique : les 19 `monkeypatch` des tests patchent tous `httpx.Client` sur
l'objet module (`oktime.httpx` *est* `httpx`), donc ils continuent d'intercepter
la fabrique. Un import direct du symbole les rendrait tous muets, sans qu'aucun
test échoue pour autant — ils passeraient en tapant le réseau.

Forme au site d'appel :

```python
# avant
with httpx.Client(follow_redirects=True, timeout=30, headers=HEADERS) as client:
# après
with http.client(timeout=30, headers=HEADERS) as client:
```

### 2. La politique : `not ip.is_global`

Pour chaque destination — requête initiale **et** chaque saut :

1. **Schéma** hors `http`/`https` → `BlockedTargetError`. Ce contrôle **porte**,
   il n'est pas de la défense en profondeur : mesuré, dès lors qu'un `transport=`
   explicite est fourni, httpx n'écarte plus les autres schémas avant d'appeler
   le transport. `ftp://exemple.fr/x` y arrive tel quel, et un
   `302 → file:///etc/passwd` y arrive réécrit en `file://<host>/etc/passwd`,
   répété jusqu'à `TooManyRedirects` (20 passages au transport).
2. **Host** : littéral d'IP, vérifié tel quel ; sinon `getaddrinfo(host, port)`,
   et **toutes** les adresses rendues doivent être publiques. Une seule adresse
   interne suffit à refuser — un host hostile publie souvent les deux.
3. **Échec de résolution** (`socket.gaierror`) : on **ne refuse pas**, on laisse
   httpx lever sa `ConnectError` habituelle. Un DNS mort n'est pas une alerte de
   sécurité, et le déguiser en refus de destination enverrait l'opérateur
   chercher une attaque là où il y a une panne.

Le prédicat est `not ip.is_global`, appliqué à la forme IPv4 quand l'adresse est
IPv4-mapped. Il a été **mesuré contre** la disjonction explicite
(`is_private or is_loopback or is_link_local or is_reserved or is_multicast or
is_unspecified`) :

| Adresse | disjonction | `not is_global` |
| --- | --- | --- |
| `169.254.169.254`, `127.0.0.1`, `10.0.0.5`, `192.168.1.1`, `172.16.0.1` | refusée | refusée |
| `::1`, `fe80::1`, `fc00::1`, `0.0.0.0`, `::ffff:127.0.0.1` | refusée | refusée |
| `192.0.2.1` (TEST-NET) | refusée | refusée |
| `100.64.0.1` (CGNAT, RFC 6598) | **acceptée** | refusée |
| `8.8.8.8`, `2001:4860:4860::8888` | acceptée | acceptée |

Un prédicat au lieu de six, et il ferme la plage CGNAT que la disjonction
laissait passer. Il n'écarte rien de légitime : les **14 hosts fournisseurs** du
panel, résolus pour de vrai (RaceResult, Klikego, Breizh Chrono, TimePulse,
T2Area, RunnerBreizh, ok-time, Competitor, Chronoplace, ChronoWest, ProLiveSport,
Sportinnovation, plus `docs.google.com` et `nominatim.openstreetmap.org`) donnent
**24 adresses, aucune refusée**.

La normalisation `ipv4_mapped` reste écrite explicitement bien que `is_private`
couvre déjà `::ffff:127.0.0.1` sur Python 3.13 : c'est une garantie du contrat,
pas un détail d'implémentation de la version courante, et un test la verrouille.

### 3. Un mémo de résolution par client

`getaddrinfo` coûte **21 à 28 ms** sur cette machine, sans cache OS observable
(trois mesures consécutives sur `my.raceresult.com` : 28,6 / 21,1 / 20,9 ms).
T2Area fait ~26 requêtes vers le même host sur une épreuve (le classement plus
une fiche par membre du TCN), Sportinnovation davantage : sans mémo, le garde
ajouterait ~0,6 s par import, pour rien.

Le mémo est un `dict` d'instance du transport, sans TTL : sa durée de vie est
celle du client, c'est-à-dire un scrape. Aucune invalidation à écrire.

### 4. `BlockedTargetError`, et surtout ce dont elle n'hérite pas

Elle dérive de `DomainError` (422) et **jamais** de `ValueError`.
`import_service._scrape_all:72` attrape `ValueError` pour dire « fournisseur non
supporté » : une destination refusée s'y afficherait comme un problème de
provider. En dérivant de `DomainError`, elle tombe dans le `except Exception` de
la ligne 74 et ressort en `ScraperError` avec sa cause — donc visible dans le
détail des épreuves en erreur des bilans CLI. Un test verrouille la
non-parenté.

## Tests

Un fichier neuf, `tests/test_core_http.py` :

- **Politique** — le panel de 14 adresses ci-dessus, verrouillé tel quel,
  `100.64.0.1` et `::ffff:127.0.0.1` compris.
- **Blocage effectif** — un `MockTransport` interne répondant
  `302 → http://169.254.169.254/…` ; on assert que le transport interne **ne voit
  jamais** la seconde URL. C'est ce qui prouve que la requête ne part pas, et non
  seulement qu'une exception sort.
- **Redirection cross-host légitime** — `docs.google.com` →
  `googleusercontent.com`, le cas réel de `sheet_source`, doit passer. C'est le
  test qui interdit de resserrer plus tard vers une allowlist de hosts sans s'en
  apercevoir.
- **`gaierror` → `ConnectError`**, pas `BlockedTargetError`.
- **Mémo** — deux requêtes vers le même host, un seul `getaddrinfo` (compteur
  monkeypatché).
- **`not issubclass(BlockedTargetError, ValueError)`**.
- **Schéma non-http** refusé, dans les deux formes mesurées : une URL `ftp://`
  demandée directement, et une `302 → file:///etc/passwd`.

Plus un **méta-test** : scan de `app/**/*.py` pour `httpx.Client(`, `httpx.get(`,
`httpx.post(`, `httpx.stream(`, `httpx.request(` hors `app/core/http.py`. La
parenthèse suffit à ne pas mordre sur les annotations (`client: httpx.Client)`).
C'est le pendant de `HostMatchedProvider` en #49 : il n'y a plus de politique à
écrire au prochain scraper, et l'oubli devient une erreur de test.

**Critère de non-régression** : `uv run pytest -m "not integration"` reste vert
**sans qu'un seul test existant soit modifié**. Les deux espions qui assertent
`follow_redirects is True` (`test_competitor.py:484`, `test_raceresult.py:2336`)
continuent de passer, la fabrique posant ce kwarg. Avant merge, un passage
`-m integration` : c'est la seule vérification des redirections légitimes en
conditions réelles.

## Décisions écartées

**Allowlist de hosts par provider** (piste 2 du ticket, `registry._host_match` à
chaque saut). Écartée : elle casse `sheet_source` — l'export CSV d'un Google
Sheet redirige vers `googleusercontent.com`, un autre domaine — et elle exige de
faire descendre le contexte du provider jusqu'au client. Elle ne ferme pas
davantage : le rebinding DNS d'un host fournisseur légitime lui échappe aussi.

**`event_hook` sur `response`** (piste 1 du ticket, seconde variante). Écartée :
ne voit pas la requête initiale, et oblige à rejoindre soi-même une `Location`
relative que httpx sait déjà résoudre. Voir le tableau du sondage.

**Épinglage de l'IP validée** (connexion forcée vers l'adresse vérifiée, en
conservant `Host` et SNI). Écartée : ferme le rebinding pour de bon, mais touche
au TLS — SNI à forcer à la main, vérification de certificat à ne pas casser — et
dépend de détails d'httpx/httpcore qu'aucun test hors réseau ne couvre. Le
bénéfice ne paie pas ce risque-là sur un vecteur qui exige déjà de contrôler un
host fournisseur.

**Littéraux d'IP seulement**, sans résolution DNS. Écartée : ferme l'exemple du
ticket (`302 → http://169.254.169.254/`) mais pas la classe d'attaque — un
`302 → http://interne.corp/`, ou un host qui résout vers `10.0.0.5`, passerait.

**Fabrique sans méta-test.** Écartée pour la raison qui a fait écarter « fonction
libre seule » en #49 : le correctif protégerait aujourd'hui sans protéger demain,
rien n'empêchant le prochain scraper d'écrire `httpx.Client(...)` nu.

## Résidus connus

**Le garde résout un nom, il ne contrôle pas la connexion.** C'est le résidu
générique, dont les autres sont des instances : `_check_target` interroge *son*
résolveur, httpcore ouvre *sa* socket, et rien n'oblige les deux à désigner la
même machine. Toute divergence entre ces deux chemins — de nom ou d'adresse —
est un contournement potentiel du garde. Il s'en connaît deux :

- **la divergence de nom** (fermée). `url.host` est l'Unicode, ré-encodé par
  `getaddrinfo` avec le codec `idna` de CPython, soit IDNA 2003 ; httpcore joint
  `url.raw_host`, produit par httpx avec idna 2008. Sur ß, sigma final ou
  ZWJ/ZWNJ ce sont deux domaines enregistrables distincts (`faß.example` →
  `fass.example` contre `xn--fa-hia.example`). Le garde résout désormais
  `raw_host`, le nom du fil ;
- **la divergence d'adresse** (ouverte) : le TOCTOU / rebinding DNS ci-dessous.

Le seul correctif qui referme la classe entière est l'épinglage de l'adresse
validée jusqu'à la connexion — écarté plus haut. À défaut, tout changement
touchant la façon dont le garde nomme ou résout sa cible se relit avec cette
question : est-ce bien ce qu'httpcore joindra ?

**TOCTOU / rebinding DNS.** httpx résout une seconde fois pour se connecter, et
le mémo par client élargit la fenêtre. Un DNS hostile pourrait rendre une adresse
publique à la vérification et une adresse interne à la connexion. Assumé : voir
« Épinglage de l'IP validée » ci-dessus.

**Redirection vers un host non-fournisseur, désormais autorisée par
construction.** C'est le prix de la politique par classe d'IP, et le test Google
Sheet en fait un choix visible plutôt qu'un angle mort.

**`playwright_fallback.py`, code mort.** Déjà signalé par le design de #49,
toujours hors périmètre : c'est le seul module capable de naviguer vers une URL
arbitraire, mais rien ne l'appelle. Ticket propre à ouvrir.
