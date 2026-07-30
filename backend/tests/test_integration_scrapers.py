"""
Tests d'intégration des scrapers — appels réseau RÉELS (marker `integration`).

Hors CI par défaut. Lancer explicitement :
    pytest -m integration

Vérifie la voie unique `scrape_event_all` sur une épreuve réelle par provider.
Les URLs (événements passés/stables) sont documentées dans
`docs/superpowers/specs/2026-06-08-scrapers-audit-report.md`.

Assertions volontairement souples (les données d'épreuve évoluent) : le scraper
doit renvoyer ≥1 participant avec au moins un nom et un temps total peuplés.
"""
import time
from collections import Counter
from datetime import date

import pytest

from app.core.club import is_tcn
from app.scrapers import breizhchrono, klikego, registry

# URLs réelles fonctionnelles, une par provider.
# prolivesport : forme front `/result/{eventId}/{index}` (l'index 6 = course "S").
LIVE_URLS = {
    "klikego": "https://www.klikego.com/resultats/triathlon-de-vierzon-2026/1674523163798-4",
    "breizhchrono": (
        "https://resultats.breizhchrono.com/resultats-courses/"
        "triathlon-de-la-cote-de-granit-rose-tregastel-2026-1295405190290-19/triathlon-m"
    ),
    "wiclax": "https://chronosmetron.wiclax-results.com/Triathlon%20de%20la%20Roche%202026/",
    "timepulse": "https://www.timepulse.fr/epreuves/resultats/live/3232",
    "prolivesport": "https://www.prolivesport.fr/result/1082/6",
    "sportinnovation": "https://sportinnovation.fr/Evenements/Resultats/7031",
    # Triathlon de Rumilly 2026 : 4 contests, dossards en collision d'un contest
    # à l'autre — l'épreuve qui a servi au sondage d'API initial.
    "raceresult": "https://my3.raceresult.com/393893/results",
    "chronoplace": "https://www.chronoplace.fr/classement/spaycific-races-2025/epreuve/494",
    # fftri.t2area.com : plateforme officielle FFTRI, édition figée (901 lignes).
    "t2area": (
        "https://fftri.t2area.com/calendrier/triathlon-de-la-baule/triathlon-m/2022.html"
    ),
    # IRONMAN France : page « Results » d'ironman.com → iframe Competitor. Deux
    # sauts (page → uuid → __NEXT_DATA__) et l'édition la plus récente publiée.
    "competitor": "https://www.ironman.com/races/im-france/results",
    # Triathlon de Lacanau 2026 : 5 épreuves partageant date et type — l'épreuve
    # qui a servi au sondage d'API. La forme `/race/<id>` est celle du Sheet.
    "oktime": "https://classement.ok-time.fr/48555/race/59697",
    # runnerbreizh : épreuve du Sheet, 322 classés sur 7 pages. L'URL est donnée
    # avec `&page=2`, la forme réellement collée par les contributeurs : le
    # scraper doit repartir de la page 1.
    "runnerbreizh": (
        "https://www.runnerbreizh.fr/requetetriathlons.php"
        "?CourseFichierGpsNom=2025-09-0749quiberon&page=2&tricourse=&Sexe="
    ),
    # Sporthive : l'unique lien du Sheet, dossard 426 du Triathlon S de Sud
    # Vendée 2024 — un membre du TCN. La forme `/races/1/bib/{b}` est celle du
    # Sheet, et son `1` est un **ordinal local** : cf. le test dédié.
    "sporthive": (
        "https://results.sporthive.com/events/7237011278055708416/races/1/bib/426"
    ),
    # Triathlon d'Oléron 2024 : 3 épreuves, 854 participants publiés. L'URL est
    # donnée avec son paramètre d'épreuve, la forme réellement collée par les
    # contributeurs : le scraper doit importer l'événement entier.
    "chronoweb": "https://chronoweb.com/resultats_evenement.php?event=323&epreuve=1147",
}

#: Hors de `LIVE_URLS`, qui est indexé **par provider** — une seconde entrée
#: chronoweb y écraserait la première et ferait disparaître ce contrôle.
CHRONOWEB_DIJON = "https://chronoweb.com/resultats_evenement.php?event=371"


@pytest.mark.integration
@pytest.mark.parametrize("provider, url", sorted(LIVE_URLS.items()))
def test_detection(provider, url):
    """L'URL est routée vers le bon provider."""
    assert registry.detect_provider(url) == provider


@pytest.mark.integration
@pytest.mark.parametrize("provider, url", sorted(LIVE_URLS.items()))
def test_scrape_event_all_live(provider, url):
    """L'import d'épreuve renvoie des participants exploitables."""
    results = registry.scrape_event_all(url)
    assert results, f"{provider} : aucun participant renvoyé"
    assert any(r.athlete_name for r in results), f"{provider} : aucun nom d'athlète"
    assert any(r.total_time for r in results), f"{provider} : aucun temps total"
    # Type d'épreuve détecté sur au moins un résultat
    assert any(r.event_type for r in results), f"{provider} : type d'épreuve non détecté"


@pytest.mark.integration
def test_sportinnovation_2026_race_url():
    """Forme 2026 results.sportinnovation.fr/race/{slug} (niveau course, API JSON)."""
    url = "https://results.sportinnovation.fr/race/zmhc-triathlon-m"
    results = registry.scrape_event_all(url)
    assert results
    assert any(r.athlete_name and r.total_time for r in results)
    assert any(r.event_type for r in results)


@pytest.mark.integration
def test_prolivesport_includes_non_finishers():
    """prolivesport renvoie désormais finishers ET non-finishers, chacun statué."""
    url = LIVE_URLS["prolivesport"]
    results = registry.scrape_event_all(url)
    assert results, "prolivesport : aucun participant renvoyé"
    statuses = {r.status for r in results}
    assert "finisher" in statuses, "prolivesport : aucun finisher"
    assert any(s != "finisher" for s in statuses), (
        f"prolivesport : aucun non-finisher (statuts vus : {statuses})"
    )
    # Un non-finisher n'a ni temps total ni rang.
    for r in results:
        if r.status != "finisher":
            assert not r.total_time, f"{r.status} avec un temps total : {r.total_time}"
            assert r.rank_overall is None, f"{r.status} avec un rang : {r.rank_overall}"


@pytest.mark.integration
def test_timepulse_conserve_non_finishers():
    """Le fix TimePulse conserve les non-finishers s'il y en a (best-effort).

    Données réelles évolutives → pas d'assertion stricte sur le nombre. On vérifie
    que des finishers remontent et on documente le nombre de non-finishers
    conservés (un <E> sans <R> → total_time vide).
    """
    results = registry.scrape_event_all(LIVE_URLS["timepulse"])
    assert results, "timepulse : aucun participant"
    assert any(r.total_time for r in results), "timepulse : aucun finisher"
    non_finishers = [r for r in results if not r.total_time]
    print(
        f"timepulse non-finishers conservés : {len(non_finishers)}/{len(results)}"
    )


@pytest.mark.integration
@pytest.mark.parametrize("provider, url", sorted(LIVE_URLS.items()))
def test_scrape_event_all_status_jamais_incoherent(provider, url):
    """Garde-fou : un résultat avec statut non-finisher n'a pas de temps total.

    Vérifie l'hygiène cross-provider (DNF/DNS/DSQ ⇒ total_time vide).
    """
    results = registry.scrape_event_all(url)
    for r in results:
        if r.status in ("DNF", "DNS", "DSQ"):
            assert not r.total_time, (
                f"{provider} : {r.athlete_name} statut {r.status} mais temps {r.total_time!r}"
            )


@pytest.mark.integration
def test_bc_audencia_la_baule_exhaustif():
    results = breizhchrono.scrape_event_all(
        "1488071608761-572", "triathlon-s-light",
        "Triathlon Audencia La Baule 2024", "triathlon-audencia-la-baule-2024",
    )
    assert len(results) == 591
    assert sum(1 for r in results if not r.status) == 483       # finishers
    assert sum(1 for r in results if r.status == "DNF") >= 1
    assert sum(1 for r in results if r.status == "DNS") >= 1
    # splits inter présents pour les finishers (event avec checkpoints)
    assert any(r.bike_time for r in results if not r.status)


@pytest.mark.integration
def test_bc_live_dinard_swimrun():
    """live.breizhchrono.com routé vers le moteur Klikego (issue #34).

    Un heat unique de l'épreuve Dinard 2025 (plus gros volume du Sheet). On cible
    un heat descriptif pour vérifier la classification heat-seul (le slug de
    l'événement contient « swimrun » et ne doit PAS polluer un heat triathlon).
    """
    url = (
        "https://live.breizhchrono.com/external/live5/classements.jsp"
        "?version=new&reference=1488071608761-688&heat=triathlon-distance-olympique"
    )
    assert registry.detect_provider(url) == "breizhchrono"
    results = registry.scrape_event_all(url)
    assert results, "live BC : aucun participant renvoyé"
    assert any(r.athlete_name for r in results)
    assert any(r.total_time for r in results)
    # Classification correcte malgré le slug « swimrun » de l'événement.
    assert any(r.event_type == "triathlon-m" for r in results)
    # La date vient d'index.jsp (classements.jsp n'en porte aucune) et elle est
    # propre au heat : l'olympique court le 14/09, le trail de la même épreuve le 12.
    assert all(r.event_date == date(2025, 9, 14) for r in results)
    # Le nom porte le libellé du heat, sans quoi les heats d'une même épreuve
    # fusionnent sur l'identité de course (nom, date, type, relais).
    assert all(
        r.event_name.endswith("— Triathlon Distance Olympique") for r in results
    )
    # Statut cohérent : un non-finisher n'a pas de temps total.
    for r in results:
        if r.status in ("DNF", "DNS", "DSQ"):
            assert not r.total_time


@pytest.mark.integration
def test_klikego_nozeen_exhaustif():
    results = klikego.scrape_event_all(
        "1517534975128-8", "duathlon-s---open",
        "6e Duathlon Nozeen 2026", "6e-duathlon-nozeen-2026",
    )
    assert len(results) == 166
    assert sum(1 for r in results if not r.status) == 139           # finishers
    # 27 non-classés (166 - 139) : mélange DNF + DNS/DSQ selon le millésime.
    # Le data block expose bien les statuts (l'ancien endpoint les omettait).
    assert sum(1 for r in results if r.status) == 27
    assert sum(1 for r in results if r.status == "DNF") >= 1


@pytest.mark.integration
def test_chronowest_deploiement_wiclax():
    """chronowest.fr = déploiement WordPress + iframe G-Live (issue #35).

    Épreuve terminée et stable. Ne PAS utiliser /resultats/armorun-2025/ :
    son .clax a été réinitialisé pour l'édition 2026 (pas encore courue) et ne
    contient plus ni <Engages> ni <Resultats> — 0 résultat, alors que le scraper
    fonctionne.
    """
    url = "https://chronowest.fr/resultats/trail-des-2-ponts-2026/"
    assert registry.detect_provider(url) == "wiclax"
    results = registry.scrape_event_all(url)
    assert len(results) > 100, f"chronowest : seulement {len(results)} participants"
    assert any(r.athlete_name and r.total_time for r in results)
    assert all(r.event_type == "trail" for r in results if r.event_type)


@pytest.mark.integration
def test_chronowest_apostrophe_dans_le_nom_de_fichier():
    """Non-régression du src d'iframe tronqué : LOC'orrida 2026.clax → 404."""
    results = registry.scrape_event_all("https://chronowest.fr/resultats/locorrida-2026/")
    assert results, "locorrida : aucun participant (src d'iframe tronqué à l'apostrophe ?)"


@pytest.mark.integration
def test_chronowest_swimrun_nest_pas_un_triathlon():
    """Les parcours (« S Duo », « M Solo ») ne nomment pas le sport : il vient du
    nom d'épreuve, sinon le classifieur retombe sur triathlon."""
    results = registry.scrape_event_all("https://chronowest.fr/resultats/red-ouf-2026/")
    assert results
    types = {r.event_type for r in results}
    assert types <= {"swimrun", "swimrun-s", "swimrun-m", "swimrun-l"}, types


# Panel RaceResult : la première version du moteur ne fonctionnait QUE sur
# l'épreuve qui avait servi à la construire (revue de branche : 5 défauts
# bloquants, tous invisibles sans trafic réel au-delà d'elle). Ces épreuves
# couvrent les trois façades et les formes d'API qui l'avaient mise en défaut.
# Cf. docs/superpowers/specs/2026-07-19-raceresult-api-sondage.md.
RACERESULT_PANEL = {
    # 13 contests, relais, libellés i18n.
    "geneve": "https://my4.raceresult.com/405215/results",
    # Les 10 listes portent `Live: 1`, dont les 3 vrais classements : filtrer
    # sur `Live` plutôt que sur `Mode` y vide l'épreuve entière (C-C).
    "foulee": "https://my2.raceresult.com/405100/results",
    # Groupes de niveau 2 par SEXE (`#1_Masculin`), pas par statut (C-E).
    "besancon": "https://my4.raceresult.com/406212/results",
    # Façade espace-competition.com — identifiant nu dans `new RRPublish(...)`.
    "espace_competition": (
        "https://www.espace-competition.com/index.php"
        "?module=sportif&action=resultat&comp_uid=3205"
    ),
    # Façade chronoconsult.fr — identifiant ENTRE GUILLEMETS (C-D).
    "chronoconsult": "https://chronoconsult.fr/result/2026-24h-roller-le-mans/",
    # Témoin C1 : liste d'affichage {Selector.Splits} non-`hidden` → 42/42 sans
    # temps avant correctif. Aussi le témoin de K2 : les clés de groupe de niveau
    # 0 y sont `Finish` / `Run - Start`, des sélecteurs de point de chrono.
    "besancon_para": "https://my.raceresult.com/406211/results",
    # Témoin C2+C3 : concaténation imbriquée dans `if(…)` et rang collé aux
    # segments → 0 segment sur un half-ironman avant correctif.
    "annecy": "https://my.raceresult.com/401699/results",
    # Témoin C4 : `Finish.GUN`/`Finish.CHIP` → 58/58 sans temps avant correctif.
    "pontcharra": "https://my.raceresult.com/380823/results",
}

# Épreuves dont un `total_time` est attendu sur la quasi-totalité des lignes.
# Les autres publient des listes légitimement sans chrono (inscrits, qualifs),
# cf. `test_raceresult_panel_multi_epreuves`.
RACERESULT_ATTEND_TEMPS = {
    "besancon_para": 1.0,   # C1 : 42/42 sans temps → 0
    "annecy": 0.75,         # 145/587 DNS/DNF/DSQ légitimes
    "pontcharra": 0.90,     # C4 : 58/58 sans temps → 3 (tous DNS)
    "geneve": 0.90,
}


@pytest.mark.integration
@pytest.mark.parametrize("cle, url", sorted(RACERESULT_PANEL.items()))
def test_raceresult_panel_multi_epreuves(cle, url):
    """Chaque épreuve du panel remonte des participants nommés, non dupliqués.

    Le `total_time` n'est exigé que sur les épreuves de `RACERESULT_ATTEND_TEMPS` :
    les autres publient des listes légitimement sans chrono (liste d'inscrits,
    classement de qualification). Le nom, lui, est exigé partout — c'est ce qui
    manquait à 506 lignes sur 507 avant l'élargissement du vocabulaire
    d'expressions (C-E).

    La garde anti-duplication est celle qui manquait pour attraper K1 : le
    libellé de contest sert **à la fois** de qualifiant de `Course` et de clé de
    fusion, si bien qu'un mauvais repli produit simultanément une `Course`
    fantôme et une duplication de participations. `UNIQUE(course_id, bib_number)`
    ne s'y oppose pas — les `Course` sont distinctes — donc la perte est
    silencieuse. Mesuré sur 409130 : 302 dossards dans plusieurs `Course`.
    """
    results = registry.scrape_event_all(url)

    assert results, f"{cle} : aucun participant renvoyé"
    nommes = [r for r in results if r.athlete_name or r.athlete_firstname]
    assert len(nommes) >= 0.95 * len(results), (
        f"{cle} : {len(results) - len(nommes)}/{len(results)} lignes sans nom"
    )
    assert all(r.bib_number for r in results), f"{cle} : dossard manquant"

    # K1 : aucun dossard ne doit apparaître sous deux `event_name`.
    courses_par_dossard: dict[str, set[str]] = {}
    for r in results:
        courses_par_dossard.setdefault(r.bib_number, set()).add(r.event_name)
    multi = {b: c for b, c in courses_par_dossard.items() if len(c) > 1}
    assert not multi, (
        f"{cle} : {len(multi)} dossard(s) présents dans plusieurs Course "
        f"(duplication silencieuse) — ex. {dict(list(multi.items())[:2])}"
    )

    # Aucun `event_name` ne doit porter un nom interne de liste RaceResult : le
    # `|` est un séparateur d'affichage, jamais un qualifiant de Course (K1).
    assert all("|" not in r.event_name for r in results), (
        f"{cle} : nom de liste employé comme qualifiant de Course"
    )

    seuil = RACERESULT_ATTEND_TEMPS.get(cle)
    if seuil is not None:
        avec = [r for r in results if r.total_time]
        assert len(avec) >= seuil * len(results), (
            f"{cle} : seulement {len(avec)}/{len(results)} lignes avec un temps"
        )


@pytest.mark.integration
def test_raceresult_route_heritee_ne_couvre_pas_les_epreuves_recentes():
    """C-A, garde vivante. La route `/{id}/RRPublish/data/config` employée par
    la première version est un alias hérité : elle répond 404 sur les épreuves
    de la saison en cours. Ce test échouera si RaceResult la généralise un
    jour — auquel cas la note du sondage sera à revoir, mais jamais dans le
    sens d'un retour à l'alias.
    """
    import httpx

    from app.scrapers import raceresult

    with httpx.Client(follow_redirects=True, timeout=30) as client:
        heritee = client.get(
            "https://my4.raceresult.com/405215/RRPublish/data/config",
            params={"page": "results"}, headers=raceresult.HEADERS,
        )
        canonique = client.get(
            f"{raceresult._API_BASE}/405215/results/config",
            params={"page": "results"}, headers=raceresult.HEADERS,
        )

    assert heritee.status_code == 404, "l'alias hérité répondrait de nouveau ?"
    assert canonique.status_code == 200
    assert canonique.json()["TabConfig"]["Lists"], "les listes sont sous TabConfig"


@pytest.mark.integration
def test_raceresult_contests_et_non_finishers():
    """RaceResult : une Course par contest, non-finishers statués et purgés.

    Resserré après C1 (revue) : une liste d'affichage LIVE (`Live: 1`,
    `03 - Affichages|LIVE EXTRA sans predictif`) écrasait le vrai classement
    du contest « Distance Jeunes » et vidait 49 des 874 participants (temps,
    rang, statut). L'ancienne version de ce test ne pouvait pas l'attraper :
    la boucle exemptait explicitement le statut vide (`r.status not in ("",
    "finisher")`) et n'exigeait aucun temps sur les finishers.
    """
    results = registry.scrape_event_all(LIVE_URLS["raceresult"])
    assert results, "raceresult : aucun participant renvoyé"

    # Plusieurs contests → plusieurs noms d'épreuve qualifiés.
    assert len({r.event_name for r in results}) >= 2, (
        f"raceresult : un seul contest vu ({ {r.event_name for r in results} })"
    )
    statuses = {r.status for r in results}
    assert "finisher" in statuses, f"raceresult : aucun finisher (vus : {statuses})"

    # Un finisher a TOUJOURS un temps (C1 : une liste d'affichage LIVE ne doit
    # plus jamais écraser le vrai classement par une ligne vidée).
    assert all(r.total_time for r in results if r.status == "finisher"), (
        "raceresult : au moins un finisher sans temps total (régression C1)"
    )
    for r in results:
        if r.status not in ("", "finisher"):
            assert not r.total_time, f"{r.status} avec un temps total : {r.total_time}"
            assert r.rank_overall is None, f"{r.status} avec un rang : {r.rank_overall}"

    # Borne sur la proportion de lignes vidées (ni temps ni statut) : le bug
    # C1 en produisait 49/874 (~5,6 %) via la liste d'affichage LIVE.
    videes = [r for r in results if not r.total_time and not r.status]
    taux = len(videes) / len(results)
    assert taux < 0.02, (
        f"raceresult : {len(videes)}/{len(results)} lignes sans temps ni statut "
        f"({taux:.1%}) — régression C1 ?"
    )

    # Segments étiquetés plutôt que les 5 slots positionnels.
    assert any(r.segments for r in results), "raceresult : aucun segment"


@pytest.mark.integration
def test_raceresult_406211_enrichit_les_splits_en_reel():
    """#60 réseau réel : le classement hidden du 406211 doit apporter les splits
    aux finishers. Assertions souples (données vivantes) : au moins une dizaine
    de participants portent 5 segments Swim/T1/Bike/T2/Run."""
    from app.scrapers import raceresult

    res = raceresult.scrape_event_all("https://my.raceresult.com/406211/results")

    avec_splits = [r for r in res if r.segments]
    assert len(avec_splits) >= 10
    cinq = [r for r in avec_splits if len(r.segments) == 5]
    assert cinq, "aucune ligne live ne porte 5 segments"
    ref = cinq[0]
    assert {lab for lab, _ in ref.segments} == {"Swim", "T1", "Bike", "T2", "Run"}


@pytest.mark.integration
def test_chronoplace_importe_les_epreuves_soeurs():
    """Un seul lien couvre le triathlon et le swimrun de Spay'cific Races 2025."""
    results = registry.scrape_event_all(LIVE_URLS["chronoplace"])

    assert len(results) > 200, "le classement complet (perPage=all) n'a pas été rendu"
    assert {"triathlon-s", "swimrun"} <= {r.event_type for r in results}
    # Assertion volontairement stricte : le scraper avale l'échec de l'annuaire
    # (`_fetch_event_date` → None), donc c'est le seul garde-fou sur la date face
    # au site réel. Conditionnelle, elle resterait verte après une rupture du
    # markup de /recherche — exactement le jour où il faudrait le savoir.
    assert any(r.event_date == date(2025, 9, 21) for r in results), (
        "date absente ou fausse : annuaire /recherche indisponible, ou markup "
        "des cartes changé (cf. _parse_event_date)"
    )
    # Splits triathlon peuplés, et le TCN est bien présent.
    tri = [r for r in results if r.event_type == "triathlon-s"]
    assert any(r.swim_time and r.bike_time and r.run_time for r in tri)
    assert any("TRIATHLON CLUB NANTAIS" in (r.club or "") for r in tri)


@pytest.mark.integration
def test_chronoplace_slug_obsolete_leve():
    """Lien mort du Sheet : le site exige la paire slug + id exacte."""
    with pytest.raises(ValueError, match="slug obsolète ou épreuve retirée"):
        registry.scrape_event_all(
            "https://www.chronoplace.fr/classement/spay-swimrun-2025/epreuve/566"
        )


@pytest.mark.integration
def test_t2area_epreuve_complete():
    """La Baule M 2022 : classement complet en une requête, splits des seuls TCN."""
    results = registry.scrape_event_all(LIVE_URLS["t2area"])

    assert len(results) > 800
    assert min(r.rank_overall for r in results if r.rank_overall) == 1
    assert any(r.club and "NANTAIS" in r.club.upper() for r in results)
    assert all(r.event_date == date(2022, 9, 18) for r in results)
    # La promesse « splits des seuls TCN » : au moins un membre du club porte un
    # temps de natation, chargé via la fiche individuelle.
    assert any(is_tcn(r.club) and r.swim_time for r in results)


@pytest.mark.integration
def test_runnerbreizh_importe_toute_lepreuve_depuis_une_page_intermediaire():
    """322 classés sur 7 pages, alors que l'URL du Sheet pointe la page 2.

    Vérifie sur le site réel les deux invariants qui ne se voient pas sur fixture :
    le nombre de classés annoncé par le site est atteint, et le nom d'épreuve
    enregistré ne porte pas le détail des distances (sans quoi la carte ne
    localiserait pas l'épreuve).
    """
    results = registry.scrape_event_all(LIVE_URLS["runnerbreizh"])

    annonces = {r.raw_data.get("field_size") for r in results}
    assert annonces == {len(results)}, (
        f"runnerbreizh : {len(results)} importés pour {annonces} annoncés"
    )
    assert all(r.event_name == "Triathlon de Quiberon M" for r in results)
    assert all(not r.bib_number and not r.club for r in results)


#: Classés annoncés par `/events/{id}/races` pour les 6 courses de l'événement du
#: Sheet, mesurés au sondage du 29/07/2026 (32 courses, égalité vérifiée 32/32).
_SPORTHIVE_CLASSES = [28, 29, 47, 103, 366, 382]


@pytest.mark.integration
def test_sporthive_importe_tout_levenement_sans_epreuve_etrangere():
    """Triathlon Sud Vendée 2024 : 6 courses, 955 participations, ≈ 100 requêtes.

    C'est le test qui casse **en premier** si MYLAPS redéplace son API (D13) —
    c'est déjà arrivé une fois, l'hôte annoncé par l'issue #53 ne présente plus
    qu'un certificat `*.azurewebsites.net`. L'adresse fait alors autorité dans
    `GET sporthive.com/api/clientSettings`, pas dans le code du scraper.

    Deux invariants ne se voient pas sur fixture :

    - **SC-002** : chaque course atteint le nombre de classés annoncé. La garde
      de complétude écartant toute course tronquée, obtenir les 6 prouve
      qu'aucune ne l'a été ; la distribution exacte le prouve course par course.
    - **SC-004** : aucune participation n'atterrit sous une épreuve étrangère.
      L'URL porte `/races/1`, et sur la source réelle `GET /races/1` répond
      **200** en rendant une épreuve de 2015 (1 173 classés) : si l'ordinal
      était pris pour un identifiant de course, ce test verrait une autre date
      et un autre nom, sans qu'aucune erreur ne soit levée.
    """
    results = registry.scrape_event_all(LIVE_URLS["sporthive"])

    assert len(results) == 955
    par_course = Counter(r.event_name for r in results)
    assert len(par_course) == 6
    assert sorted(par_course.values()) == _SPORTHIVE_CLASSES

    # SC-004 : un seul événement, une seule date — celle de Sud Vendée 2024.
    assert all(r.event_date == date(2024, 9, 22) for r in results)
    assert all(r.event_name.startswith("Triathlon Sud Vendee Dimanche") for r in results)
    # Les deux courses de relais, et elles seules, sortent en `is_relay`.
    assert {r.event_name for r in results if r.is_relay} == {
        nom for nom in par_course if "Relais" in nom
    }

    # SC-001 : le membre du TCN du lien est bien là, avec ses splits en français.
    tcn = [r for r in results if is_tcn(r.club)]
    assert tcn, "aucune participation TCN sur l'épreuve du Sheet"
    assert any(r.bib_number == "426" for r in tcn)
    assert any(dict(r.segments or []).get("natation") for r in tcn)


@pytest.mark.integration
def test_sporthive_importe_un_evenement_identifie_par_guid():
    """Le fonds **récent** est identifié par GUID, pas par snowflake.

    Les deux familles cohabitent sur les mêmes routes ; c'est la seule chose
    que ce test ajoute au précédent, et elle ne se voit pas sur fixture — un
    motif d'URL `\\d+` refuse ici en amont de tout appel réseau, en affirmant
    que l'URL est illisible alors que le site la sert.

    2026 Europe Triathlon Junior Cup Izvorani : 3 courses, 93 classés, et des
    transitions dont le `type` vaut `Other` — leur libellé vient alors de
    `sportName`, sinon les deux sortent en « Other » / « Other (2) ».
    """
    url = (
        "https://sporthive.com/events/s/bdea2f10-1510-481c-b5ef-ef7f1926a06f"
        "/race/9c945c48-95ea-4680-bc98-cc5ea4e040c3"
    )

    results = registry.scrape_event_all(url)

    assert len(results) == 93
    assert len({r.event_name for r in results}) == 3
    assert all(r.event_date == date(2026, 7, 18) for r in results)

    coureur = next(r for r in results if r.segments)
    assert [label for label, _ in coureur.segments] == [
        "natation", "transition", "vélo", "transition", "course à pied",
    ]


@pytest.mark.integration
def test_sporthive_nappelle_jamais_lordinal_de_course_de_lurl():
    """Le pendant réseau du verrou de non-régression sur fixture (D1, FR-004).

    `GET /races/1/participants` répond 200 sur la source réelle. On le vérifie
    ici plutôt que de le supposer : si la route cessait de répondre, le test sur
    fixture continuerait de passer sans que le piège ait disparu.
    """
    import httpx

    from app.scrapers import sporthive

    with httpx.Client(timeout=20, headers=sporthive._HEADERS) as client:
        reponse = client.get(
            f"{sporthive._API_BASE}/races/1/participants", params={"page": 0, "size": 10}
        )

    assert reponse.status_code == 200, (
        "la route piège ne répond plus : le verrou de non-régression perd son objet"
    )
    etranger = reponse.json().get("content") or []
    assert etranger, "l'ordinal /races/1 rend un classement — c'est bien un piège actif"


@pytest.mark.integration
def test_chronoweb_evenement_entier_en_une_requete():
    """Oléron 2024 : 3 épreuves et 854 participants publiés, en une requête.

    Vérifie sur le site réel ce qu'aucune fixture ne peut montrer : les effectifs
    annoncés sont atteints (une ligne du tableau étant un **passage**, les compter
    donnerait 2 517), et l'événement entier sort de l'URL d'une seule épreuve.
    """
    results = registry.scrape_event_all(LIVE_URLS["chronoweb"])

    assert len(results) == 854
    assert len({r.event_name for r in results}) == 3
    assert all(r.event_date == date(2024, 10, 6) for r in results)
    assert all(r.raw_data.get("city") == "St Georges d'Oléron" for r in results)

    winner = next(r for r in results if r.bib_number == "360")
    assert winner.total_time == "02:13:26"
    assert (winner.rank_overall, winner.rank_category) == (1, 1)
    assert (winner.swim_time, winner.t1_time, winner.bike_time,
            winner.t2_time, winner.run_time) == (
        "00:24:24", "00:07:01", "01:00:09", "00:02:26", "00:39:26")


@pytest.mark.integration
def test_chronoweb_dijon_2026_le_plus_gros_evenement_du_panel():
    """8 épreuves, 1 622 participants, page de 4,5 Mo : la charge relevée au
    cadrage, et le seul contrôle réel qu'aucun participant n'est dupliqué ni omis.

    Volontairement hors de `LIVE_URLS` : ce dictionnaire est indexé par provider
    (`test_detection` y asserte `detect_provider(url) == provider`), donc une
    seconde entrée chronoweb écraserait la première.
    """
    start = time.monotonic()
    results = registry.scrape_event_all(CHRONOWEB_DIJON)
    duree = time.monotonic() - start

    assert len(results) == 1622, f"chronoweb Dijon : {len(results)} participants"
    assert len({r.event_name for r in results}) == 8
    cles = [(r.event_name, r.bib_number) for r in results]
    assert len(cles) == len(set(cles)), "chronoweb : dossard dupliqué au sein d'une épreuve"
    # ~3 s mesurées en local (research R1) : le seul environnement où la tenue en
    # mémoire ait été vérifiée. Journalisé, pas asserté — le réseau n'est pas un
    # critère de correction.
    print(f"\nchronoweb Dijon 2026 : {len(results)} participants en {duree:.1f} s")
