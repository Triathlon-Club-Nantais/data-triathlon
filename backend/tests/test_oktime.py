"""
Tests unitaires pour scrapers/oktime.py (sans réseau).

Les fixtures sont des charges API réduites, calquées sur le schéma mesuré au
panel du 2026-07-26 (cf. docs/superpowers/specs/2026-07-26-oktime-scraper-design.md).
Le schéma réel est revérifié par le test `integration` sur l'événement 48555.
"""
import html
import json
import logging
from datetime import date
from pathlib import Path

import httpx
import pytest

from app.scrapers import oktime


def test_parse_url_forme_classement():
    """`classement.ok-time.fr/<id>` : l'id du chemin EST le post-id WordPress."""
    assert oktime._parse_url("https://classement.ok-time.fr/48555") == ("48555", "")


def test_parse_url_ignore_le_segment_race():
    """L'API ne sait pas filtrer par épreuve : `/race/<id>` est sans effet."""
    assert oktime._parse_url("https://classement.ok-time.fr/48555/race/59697") == ("48555", "")


def test_parse_url_tolere_le_slash_final():
    assert oktime._parse_url("https://classement.ok-time.fr/48555/") == ("48555", "")


def test_parse_url_forme_evenement_rend_le_slug():
    """La forme éditoriale n'expose pas l'id : il faudra une requête pour le lire."""
    assert oktime._parse_url("https://ok-time.fr/evenement/triathlon-de-lacanau-2026/") == (
        "",
        "triathlon-de-lacanau-2026",
    )


@pytest.mark.parametrize(
    "url",
    [
        "https://ok-time.fr/course/format-s-individuel-3/",
        "https://ok-time.fr/competition/t24-ile-de-re-2025/",
        "https://ok-time.fr/course/triathlon-l/",
    ],
)
def test_parse_url_rejette_les_formes_obsoletes(url):
    """Les 3 URLs mortes du Sheet : erreur qualifiée, pour se lire sans enquête.

    ok-time devenant un host supporté, elles quittent `ignored_by_host` et
    deviennent des épreuves en erreur dans les bilans CLI (§2.1 du design). Le
    message doit dire pourquoi.
    """
    with pytest.raises(ValueError, match="obsolète"):
        oktime._parse_url(url)


def test_parse_url_rejette_une_page_hors_resultats():
    with pytest.raises(ValueError, match="non reconnue"):
        oktime._parse_url("https://ok-time.fr/contact/")


FIXTURES = Path(__file__).parent / "fixtures"

PAGE_EVENEMENT = (FIXTURES / "oktime_evenement_page.html").read_text(encoding="utf-8")


class FakeResponse:
    """Réponse HTTP factice, texte + JSON.

    `url` est l'URL **finale** — celle que httpx expose après avoir suivi les
    redirections. Laissée à None, `FakeClient` y met l'URL demandée : le cas sans
    redirection.
    """

    def __init__(self, contenu, status_code: int = 200, url: str | None = None):
        self.status_code = status_code
        self.url = url
        if isinstance(contenu, str):
            self.text, self._json = contenu, None
        else:
            self.text, self._json = json.dumps(contenu), contenu

    def json(self):
        if self._json is None:
            raise ValueError("réponse non-JSON")
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPError(f"HTTP {self.status_code}")


class FakeClient:
    """Client HTTP factice : sert les réponses et enregistre les URLs demandées."""

    def __init__(self, pages: dict | None = None, defaut: FakeResponse | None = None):
        self.pages = pages or {}
        self.defaut = defaut or FakeResponse("<html>404</html>", 404)
        self.calls: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get(self, url: str):
        self.calls.append(url)
        for motif, contenu in self.pages.items():
            if motif in url:
                reponse = contenu if isinstance(contenu, FakeResponse) else FakeResponse(contenu)
                reponse.url = reponse.url or url
                return reponse
        self.defaut.url = self.defaut.url or url
        return self.defaut


def test_resolve_event_id_lit_le_lien_de_classement():
    client = FakeClient({"/evenement/": PAGE_EVENEMENT})

    assert oktime._resolve_event_id(client, "triathlon-de-lacanau-2026") == "48555"
    assert client.calls == ["https://ok-time.fr/evenement/triathlon-de-lacanau-2026/"]


def test_resolve_event_id_sans_lien_leve():
    """Page 200 mais sans lien de classement : la forme `/course/triathlon-l/`
    redirigée vers le listing générique n'a aucun id à offrir."""
    client = FakeClient({"/evenement/": "<html><body>Aucun classement.</body></html>"})

    with pytest.raises(ValueError, match="aucun lien de classement"):
        oktime._resolve_event_id(client, "triathlon-l")


PAGE_LISTING = """<!DOCTYPE html><html><body>
  <h1>Tous les classements</h1>
  <a href="https://classement.ok-time.fr/48222">Triathlon d'Hourtin 2026</a>
  <a href="https://classement.ok-time.fr/48555">Triathlon de Lacanau 2026</a>
</body></html>"""


def test_resolve_event_id_refuse_une_page_redirigee_hors_evenement():
    """Un slug retiré est redirigé vers le listing générique (§2.1 du design).

    Ce listing porte les liens de **tous** les événements : en retenir le premier
    importerait les résultats d'un événement étranger sous la `source_url`
    demandée — donc sous sa clé de cache TTL — sans lever la moindre erreur.
    """
    client = FakeClient(
        {"/evenement/": FakeResponse(PAGE_LISTING, url="https://ok-time.fr/classements/")}
    )

    with pytest.raises(ValueError, match="redirigée"):
        oktime._resolve_event_id(client, "triathlon-l")


def test_resolve_event_id_accepte_un_slug_renomme():
    """Une page d'événement servie sous un autre slug est un permalien renommé,
    pas un listing : son id est le bon, on le retient sans broncher."""
    client = FakeClient({
        "/evenement/": FakeResponse(
            PAGE_EVENEMENT,
            url="https://ok-time.fr/evenement/triathlon-de-lacanau-2026-2/",
        )
    })

    assert oktime._resolve_event_id(client, "triathlon-de-lacanau-2026") == "48555"


def test_resolve_event_id_signale_plusieurs_ids(caplog):
    """Une page portant un bloc « derniers classements » rendrait plusieurs ids :
    le premier reste retenu, mais l'ambiguïté doit se voir dans les logs."""
    page = PAGE_EVENEMENT.replace(
        "</article>",
        '<a href="https://classement.ok-time.fr/48222">Hourtin</a></article>',
    )
    client = FakeClient({"/evenement/": page})

    with caplog.at_level(logging.WARNING, logger="app.scrapers.oktime"):
        assert oktime._resolve_event_id(client, "triathlon-de-lacanau-2026") == "48555"

    assert "48222" in caplog.text


def test_fetch_results_rend_la_charge():
    charge = {"success": True, "evenement_id": 48555, "count": 0, "data": []}
    client = FakeClient({"/wp-json/gmcap/v1/evenements/48555/results": charge})

    assert oktime._fetch_results(client, "48555") == charge
    assert client.calls == [
        "https://ok-time.fr/wp-json/gmcap/v1/evenements/48555/results"
    ]


def test_fetch_results_404_id_inconnu():
    client = FakeClient(
        defaut=FakeResponse({"message": "Ce post n'est pas un evenement."}, 404)
    )

    with pytest.raises(ValueError, match="introuvable"):
        oktime._fetch_results(client, "1")


def test_fetch_results_400_sans_resultats_publies():
    """Événement réel mais sans fichier de résultats : cause distincte du 404."""
    client = FakeClient(
        defaut=FakeResponse(
            {"message": "Aucun fichier_gmcap défini pour cet evenement."}, 400
        )
    )

    with pytest.raises(ValueError, match="aucun résultat publié"):
        oktime._fetch_results(client, "48555")


def test_fetch_results_500_remonte_en_erreur_http():
    """Une panne serveur n'est pas une erreur métier : elle ne doit pas être
    traduite en ValueError, qui la ferait passer pour un lien invalide."""
    client = FakeClient(defaut=FakeResponse("boom", 500))

    with pytest.raises(httpx.HTTPError):
        oktime._fetch_results(client, "48555")


def test_fetch_results_charge_sans_data_leve():
    client = FakeClient({"/results": {"success": False}})

    with pytest.raises(ValueError, match="Charge ok-time inattendue"):
        oktime._fetch_results(client, "48555")


# --------------------------------------------------------------------------- #
# Identité : mojibake, équipes, RGPD
# --------------------------------------------------------------------------- #

def test_repair_mojibake_repare_un_nom_cp1252():
    """173 participations du panel portent ce travers, sur les événements anciens."""
    assert oktime._repair_mojibake("AnaÃ¯s MOUSQUET") == "Anaïs MOUSQUET"


def test_repair_mojibake_laisse_intact_un_nom_accentue_sain():
    """Non-régression mesurée : les 1 061 noms accentués sains du panel traversent
    la réparation inchangés. Un faux positif scinderait un athlète en deux."""
    assert oktime._repair_mojibake("Anaïs MOUSQUET") == "Anaïs MOUSQUET"


@pytest.mark.parametrize("nom", ["", "Paul MARTIN", "Łukasz KOWALSKI", "T... B..."])
def test_repair_mojibake_neutre_sur_les_autres_cas(nom):
    """Chaîne vide, ASCII pur, caractère hors cp1252, nom anonymisé : inchangés."""
    assert oktime._repair_mojibake(nom) == nom


@pytest.mark.parametrize(
    "titre",
    ["Relais L", "Triathlon M Équipe", "Course Duo", "Team Challenge"],
)
def test_is_relay_course_par_le_titre(titre):
    assert oktime._is_relay_course(titre, []) is True


def test_is_relay_course_binome_non_titre():
    """Bike & Run de la pomme et de la châtaigne : « Course S » est un binôme
    qui ne le dit pas — 100 % de ses noms portent « / »."""
    runners = [{"nom": "A DUPONT / B MARTIN"}, {"nom": "C DURAND / D PETIT"}]

    assert oktime._is_relay_course("Course S", runners) is True


def test_is_relay_course_binome_isole_ne_bascule_pas_la_course():
    """« Format M individuel » : 1 nom sur 57 porte « / ». Un « au moins un »
    ferait basculer la course entière en relais."""
    runners = [{"nom": "A DUPONT / B MARTIN"}] + [{"nom": f"Paul MARTIN{i}"} for i in range(56)]

    assert oktime._is_relay_course("Format M individuel", runners) is False


def test_is_relay_course_sans_participant():
    assert oktime._is_relay_course("Triathlon S", []) is False


def test_athlete_identity_convention_prenom_nom():
    nom, prenom = oktime._athlete_identity(
        {"nom": "Valentin ROUVIER"}, is_relay=False, epreuve_id="59697"
    )

    assert (nom, prenom) == ("ROUVIER", "Valentin")


def test_athlete_identity_repare_le_mojibake_avant_de_scinder():
    nom, prenom = oktime._athlete_identity(
        {"nom": "AnaÃ¯s MOUSQUET"}, is_relay=False, epreuve_id="59697"
    )

    assert (nom, prenom) == ("MOUSQUET", "Anaïs")


def test_athlete_identity_nom_dequipe_non_mutile():
    """Précédent RaceResult (#63) : un nom d'équipe entre entier dans `nom`."""
    nom, prenom = oktime._athlete_identity(
        {"nom": "GUILLON RÉMI / CHARPENTIER EMMANUEL"}, is_relay=True, epreuve_id="59698"
    )

    assert (nom, prenom) == ("GUILLON RÉMI / CHARPENTIER EMMANUEL", "")


def test_athlete_identity_binome_isole_en_course_individuelle():
    """Garde par valeur : « / » suffit, même hors course de relais."""
    nom, prenom = oktime._athlete_identity(
        {"nom": "A DUPONT / B MARTIN"}, is_relay=False, epreuve_id="59697"
    )

    assert (nom, prenom) == ("A DUPONT / B MARTIN", "")


def test_athlete_identity_nom_dequipe_pur_en_course_relais():
    nom, prenom = oktime._athlete_identity(
        {"nom": "TEAM TCC"}, is_relay=True, epreuve_id="59698"
    )

    assert (nom, prenom) == ("TEAM TCC", "")


def test_athlete_identity_rgpd_identite_synthetique():
    """`rgpd:"N"` → nom amputé à la source (« T... B... ») : identité synthétique."""
    nom, prenom = oktime._athlete_identity(
        {"nom": "T... B...", "dossard": 927, "rgpd": "N"},
        is_relay=False,
        epreuve_id="59697",
    )

    assert (nom, prenom) == ("Anonyme 59697-927", "")


def test_athlete_identity_rgpd_sans_dossard_garde_le_nom_ampute():
    """Sans dossard, l'identité synthétique ne discrimine plus rien.

    « Anonyme 59697-None » serait le même pour tous les participants `rgpd:"N"`
    sans dossard d'une même épreuve : un seul `Athlete` agrégerait les résultats
    de plusieurs personnes, et `UNIQUE(course_id, bib_number)` ne rattraperait
    rien, `bib_number` étant vide. On s'en remet alors au nom amputé de la
    source, qui discrimine au moins autant.
    """
    nom, prenom = oktime._athlete_identity(
        {"nom": "T... B...", "dossard": None, "rgpd": "N"},
        is_relay=False,
        epreuve_id="59697",
    )

    assert (nom, prenom) == ("T... B...", "")


def test_athlete_identity_rgpd_sans_dossard_ne_fusionne_pas_deux_personnes():
    """Deux anonymes sans dossard de la même épreuve restent deux athlètes."""
    a = oktime._athlete_identity(
        {"nom": "T... B...", "dossard": None, "rgpd": "N"}, is_relay=False, epreuve_id="59697"
    )
    b = oktime._athlete_identity(
        {"nom": "M... D...", "dossard": None, "rgpd": "N"}, is_relay=False, epreuve_id="59697"
    )

    assert a != b


def test_athlete_identity_rgpd_distincte_entre_deux_epreuves():
    """`Athlete` est unique sur (nom, prénom, date de naissance) : sans la clé
    d'épreuve, les dossards 927 anonymes de deux courses fusionneraient en un
    athlète agrégeant deux personnes."""
    commun = {"nom": "T... B...", "dossard": 927, "rgpd": "N"}

    a = oktime._athlete_identity(commun, is_relay=False, epreuve_id="59697")
    b = oktime._athlete_identity(commun, is_relay=False, epreuve_id="60101")

    assert a != b


# --------------------------------------------------------------------------- #
# Statut, rangs, genre, temps
# --------------------------------------------------------------------------- #

def test_status_non_partant():
    runner = {"pris_depart": "N", "abandon": "N", "disqualifie": "N"}

    assert oktime._status(runner, course_non_chronometree=False) == "DNS"


def test_status_abandon():
    runner = {"pris_depart": "O", "abandon": "O", "disqualifie": "N"}

    assert oktime._status(runner, course_non_chronometree=False) == "DNF"


def test_status_disqualifie():
    runner = {"pris_depart": "O", "abandon": "N", "disqualifie": "O"}

    assert oktime._status(runner, course_non_chronometree=False) == "DSQ"


def test_status_dns_prioritaire_sur_dnf():
    """1 participation du panel cumule les deux : ne pas être parti prime."""
    runner = {"pris_depart": "N", "abandon": "O", "disqualifie": "N"}

    assert oktime._status(runner, course_non_chronometree=False) == "DNS"


def test_status_course_non_chronometree_est_finisher():
    """Les 3 courses enfants (UNICEF, 52 participations) : courues et déclarées
    terminées, mais sans chronométrage individuel. Sans cette règle,
    `mapping.derive_status` les classerait DNF en bloc et le front afficherait un
    badge d'abandon sur une course entière d'enfants."""
    runner = {"pris_depart": "O", "abandon": "N", "disqualifie": "N"}

    assert oktime._status(runner, course_non_chronometree=True) == "finisher"


def test_status_par_defaut_delegue_a_lheuristique():
    """Un participant sans temps dans une course par ailleurs chronométrée reste
    traité par l'heuristique du projet : rien ne le distingue d'un abandon non
    saisi."""
    runner = {"pris_depart": "O", "abandon": "N", "disqualifie": "N"}

    assert oktime._status(runner, course_non_chronometree=False) == ""


def test_status_abandon_prime_sur_course_non_chronometree():
    """Un statut explicite de la source n'est jamais écrasé par le repli."""
    runner = {"pris_depart": "O", "abandon": "O", "disqualifie": "N"}

    assert oktime._status(runner, course_non_chronometree=True) == "DNF"


def test_rank_zero_devient_none():
    """1 336 finishers valides du panel portent `classement_general: 0` (= non
    classé). `normalize_rank` rendrait 0, qui s'afficherait comme une place."""
    assert oktime._rank(0) is None


@pytest.mark.parametrize("valeur, attendu", [(1, 1), (42, 42), (None, None), ("", None)])
def test_rank_cas_courants(valeur, attendu):
    assert oktime._rank(valeur) == attendu


@pytest.mark.parametrize("brut, attendu", [("M", "M"), ("F", "F"), ("m", "M")])
def test_gender_conserve_m_et_f(brut, attendu):
    assert oktime._gender(brut) == attendu


@pytest.mark.parametrize("brut", ["X", "", None, "?"])
def test_gender_vide_hors_m_et_f(brut):
    """`X` (relais mixtes, 323 participations) : chaîne vide plutôt qu'une valeur
    que le front ne sait pas rendre."""
    assert oktime._gender(brut) == ""


def test_total_time_normalise():
    assert oktime._total_time({"temps_finish": "3:31:57"}) == "03:31:57"


@pytest.mark.parametrize("brut", ["00:00:00", "", None])
def test_total_time_absent(brut):
    """`"00:00:00"` est la façon dont la source dit « pas de temps »."""
    assert oktime._total_time({"temps_finish": brut}) == ""


# --------------------------------------------------------------------------- #
# Splits : cumulés → durées de segment
# --------------------------------------------------------------------------- #

POINTS_TRIATHLON = [
    {"id": "11|1", "nom": "NATATION", "time": "00:23:56"},
    {"id": "12|2", "nom": "VELO", "time": "02:20:10"},
    {"id": "13|3", "nom": "COURSE A PIED", "time": "03:31:57"},
]


def test_segments_differencie_les_cumules():
    """4 512 des 4 522 participations à ≥ 2 points ont des cumulés croissants."""
    segments, cumuls_conserves = oktime._segments(POINTS_TRIATHLON)

    assert segments == [
        ("NATATION", "00:23:56"),
        ("VELO", "01:56:14"),
        ("COURSE A PIED", "01:11:47"),
    ]
    assert cumuls_conserves is False


def test_segments_conserve_les_libelles_de_la_source():
    """Les `id` ne sont pas sémantiques (« 12|2 » vaut T2 ici, VELO là) et 55 des
    99 courses sortent du motif triathlon : un remapping devinerait."""
    points = [
        {"id": "1|1", "nom": "CP1", "time": "00:15:00"},
        {"id": "2|2", "nom": "CP2", "time": "00:40:00"},
    ]

    assert oktime._segments(points)[0] == [("CP1", "00:15:00"), ("CP2", "00:25:00")]


def test_segments_delta_negatif_replie_sur_les_bruts():
    """Mimizan : `Vélo 01:30:46` puis `T2 01:30:19` — ordre incohérent à la
    source, 10 participations. Mieux vaut un cumulé qu'un temps absurde."""
    points = [
        {"id": "1|1", "nom": "NATATION", "time": "00:20:00"},
        {"id": "2|2", "nom": "VELO", "time": "01:30:46"},
        {"id": "3|3", "nom": "T2", "time": "01:30:19"},
    ]

    segments, cumuls_conserves = oktime._segments(points)

    assert segments == [
        ("NATATION", "00:20:00"),
        ("VELO", "01:30:46"),
        ("T2", "01:30:19"),
    ]
    assert cumuls_conserves is True


def test_segments_sans_point():
    assert oktime._segments([]) == ([], False)


def test_segments_tolere_une_liste_absente():
    assert oktime._segments(None) == ([], False)


def test_segments_ignore_les_points_sans_temps():
    """Un point à `"00:00:00"` ne porte aucune durée : le garder ferait sortir un
    delta négatif au point suivant et déclencherait le repli à tort."""
    points = [
        {"id": "0|0", "nom": "DEPART", "time": "00:00:00"},
        {"id": "1|1", "nom": "NATATION", "time": "00:23:56"},
    ]

    assert oktime._segments(points) == ([("NATATION", "00:23:56")], False)


def test_segments_un_seul_point():
    points = [{"id": "1|1", "nom": "NATATION", "time": "00:23:56"}]

    assert oktime._segments(points) == ([("NATATION", "00:23:56")], False)


# --------------------------------------------------------------------------- #
# _build_result
# --------------------------------------------------------------------------- #

RUNNER_NOMINAL = {
    "nom": "Valentin ROUVIER", "sexe": "M", "dossard": 1217,
    "club": "TRIATHLON CLUB NANTAIS", "categorie": "Senior", "categorie_abbrev": "SE",
    "temps_finish": "03:31:57", "temp-reel": None,
    "classement_general": 1, "classement_categorie": 1, "classement_sexe": 1,
    "rgpd": "O", "abandon": "N", "disqualifie": "N", "pris_depart": "O",
    "points_de_passage": POINTS_TRIATHLON,
}

CONTEXTE = {
    "epreuve_id": "59697",
    "heuredebut_course": "08:00:00",
    "reference_epreuve": "LAC-L-IND",
    "status_course": "finish",
}


def _resultat(runner, **surcharges):
    kwargs = {
        "url": "https://classement.ok-time.fr/48555",
        "event_name": "Triathlon de Lacanau 2026 - Triathlon L Individuel",
        "event_type": "triathlon-l",
        "event_date": date(2026, 5, 2),
        "distance_km": 110.0,
        "is_relay": False,
        "epreuve_id": "59697",
        "course_non_chronometree": False,
        "contexte": CONTEXTE,
    }
    kwargs.update(surcharges)
    return oktime._build_result(runner, **kwargs)


def test_build_result_champs_nominaux():
    r = _resultat(RUNNER_NOMINAL)

    assert r.provider == "oktime"
    assert r.source_url == "https://classement.ok-time.fr/48555"
    assert (r.athlete_name, r.athlete_firstname) == ("ROUVIER", "Valentin")
    assert r.club == "TRIATHLON CLUB NANTAIS"
    assert r.category == "Senior"
    assert r.gender == "M"
    assert r.bib_number == "1217"
    assert r.event_name == "Triathlon de Lacanau 2026 - Triathlon L Individuel"
    assert r.event_type == "triathlon-l"
    assert r.event_date == date(2026, 5, 2)
    assert r.distance_km == 110.0
    assert r.is_relay is False
    assert r.total_time == "03:31:57"
    assert r.status == ""


def test_build_result_range_les_splits_dans_segments():
    """Chemin générique déplafonné, pas les 5 slots positionnels."""
    r = _resultat(RUNNER_NOMINAL)

    assert r.segments == [
        ("NATATION", "00:23:56"),
        ("VELO", "01:56:14"),
        ("COURSE A PIED", "01:11:47"),
    ]
    assert (r.swim_time, r.t1_time, r.bike_time, r.t2_time, r.run_time) == ("", "", "", "", "")


def test_build_result_total_time_ne_vient_jamais_du_dernier_point():
    """392 participations ont un dernier point ≠ `temps_finish` (épreuves
    finissant sur « Départ CAP2 »). `temps_finish` fait seul foi."""
    runner = {
        **RUNNER_NOMINAL,
        "temps_finish": "01:12:00",
        "points_de_passage": [
            {"id": "1|1", "nom": "RUN1", "time": "00:20:00"},
            {"id": "2|2", "nom": "DEPART CAP2", "time": "00:55:00"},
        ],
    }

    r = _resultat(runner)

    assert r.total_time == "01:12:00"
    assert r.segments == [("RUN1", "00:20:00"), ("DEPART CAP2", "00:35:00")]


def test_build_result_dossard_absent():
    r = _resultat({**RUNNER_NOMINAL, "dossard": None})

    assert r.bib_number == ""


def test_build_result_bascule_le_drapeau_de_cumuls_conserves():
    runner = {
        **RUNNER_NOMINAL,
        "points_de_passage": [
            {"id": "1|1", "nom": "VELO", "time": "01:30:46"},
            {"id": "2|2", "nom": "T2", "time": "01:30:19"},
        ],
    }

    r = _resultat(runner)

    assert r.raw_data["splits_cumules_conserves"] is True
    assert r.segments == [("VELO", "01:30:46"), ("T2", "01:30:19")]


def test_build_result_raw_data_conserve_le_brut_et_le_contexte():
    """Une erreur de différenciation doit rester diagnosticable sans re-scraper :
    les points de passage **cumulés** d'origine sont conservés tels quels."""
    r = _resultat(RUNNER_NOMINAL)

    assert r.raw_data["temp-reel"] is None
    assert r.raw_data["categorie_abbrev"] == "SE"
    assert r.raw_data["points_de_passage"] == POINTS_TRIATHLON
    assert r.raw_data["heuredebut_course"] == "08:00:00"
    assert r.raw_data["reference_epreuve"] == "LAC-L-IND"
    assert r.raw_data["status_course"] == "finish"
    assert r.raw_data["splits_cumules_conserves"] is False


def test_build_result_rgpd_identite_synthetique_mais_resultat_publie():
    """La source ampute le nom mais publie temps et rang : on importe les deux."""
    runner = {
        **RUNNER_NOMINAL, "nom": "T... B...", "dossard": 927, "rgpd": "N", "club": "",
    }

    r = _resultat(runner)

    assert (r.athlete_name, r.athlete_firstname) == ("Anonyme 59697-927", "")
    assert r.total_time == "03:31:57"
    assert r.rank_overall == 1


def test_build_result_genre_mixte_vide():
    r = _resultat({**RUNNER_NOMINAL, "sexe": "X"})

    assert r.gender == ""


def test_build_result_rangs_zero_a_none():
    runner = {
        **RUNNER_NOMINAL,
        "classement_general": 0, "classement_categorie": 0, "classement_sexe": 0,
    }

    r = _resultat(runner)

    assert (r.rank_overall, r.rank_category, r.rank_gender) == (None, None, None)


def test_build_result_course_non_chronometree_est_finisher():
    runner = {**RUNNER_NOMINAL, "temps_finish": "00:00:00", "points_de_passage": []}

    r = _resultat(runner, course_non_chronometree=True)

    assert r.status == "finisher"
    assert r.total_time == ""


# --------------------------------------------------------------------------- #
# _course_results : niveau course
# --------------------------------------------------------------------------- #

LACANAU = json.loads((FIXTURES / "oktime_lacanau_48555.json").read_text(encoding="utf-8"))
ENGAGES = json.loads((FIXTURES / "oktime_engages_48999.json").read_text(encoding="utf-8"))

URL_48555 = "https://classement.ok-time.fr/48555"


def _courses(charge, index):
    """Les participants d'une course de la charge, titre d'événement déjà décodé."""
    return oktime._course_results(
        charge["data"][index],
        url=URL_48555,
        evenement_title=html.unescape(charge["evenement_title"]),
    )


@pytest.mark.parametrize("brut, attendu", [("02/05/2026", date(2026, 5, 2)), ("", None), (None, None)])
def test_parse_date(brut, attendu):
    assert oktime._parse_date(brut) == attendu


def test_parse_date_format_inattendu():
    assert oktime._parse_date("2026-05-02") is None


@pytest.mark.parametrize(
    "brut, attendu",
    [("110,000", 110.0), ("27,5", 27.5), ("9,500", 9.5), ("", None), (None, None), ("0,000", None)],
)
def test_parse_distance(brut, attendu):
    """Virgule décimale. Renseignée partout au panel : évite le repli sur
    l'extraction depuis le nom, qui lit « Course chronométrée 9,5 km » comme 5 km."""
    assert oktime._parse_distance(brut) == attendu


def test_course_results_nom_qualifie_par_lepreuve():
    """Sans le titre d'épreuve, les épreuves de Lacanau, qui partagent date et
    type, fusionneraient sur `uq_course_identity` et leurs dossards entreraient
    en collision (issue #21)."""
    resultats = _courses(LACANAU, 0)

    assert all(
        r.event_name == "Triathlon de Lacanau 2026 – Samedi 02 mai - Triathlon L Individuel"
        for r in resultats
    )


def test_course_results_entites_html_decodees_dans_le_nom():
    """`&#038;` partirait en base tel quel sans `html.unescape`."""
    resultats = _courses(LACANAU, 1)

    assert resultats[0].event_name.endswith("Relais L & Duo")
    assert "&#" not in resultats[0].event_name


def _course_simple(title_course: str, **surcharges) -> dict:
    """Une épreuve minimale, un participant fini : de quoi observer la seule
    classification."""
    return {
        "title_course": title_course,
        "epreuve_id": 1,
        "date_course": "02/05/2026",
        "distance_course": "12,000",
        "status": "finish",
        "runners": [{"nom": "Paul MARTIN", "temps_finish": "01:00:00"}],
        **surcharges,
    }


def test_course_results_classification_repli_sur_le_titre_devenement():
    """Le titre d'épreuve muet sur le sport se lit à la lumière de l'événement :
    « Format M individuel » du SwimRun Côte Beauté sortirait sinon en triathlon-m.
    Ce repli corrige 5 courses du panel et n'en dégrade aucune."""
    resultats = oktime._course_results(
        _course_simple("Format M individuel", distance_course="20,000"),
        url=URL_48555,
        evenement_title="SwimRun de la Côte de Beauté",
    )

    assert resultats[0].event_type == "swimrun-m"


@pytest.mark.parametrize("title_course, attendu", [
    ("Trail 12 km", "trail"),
    ("Course a pied 10 km", "course-a-pied-10k"),
    ("Cyclosportive", "cyclisme-route"),
])
def test_course_results_epreuve_annexe_garde_sa_discipline(title_course, attendu):
    """Une épreuve annexe d'un « Triathlon de X » n'est pas un triathlon.

    Classée sur la concaténation des deux titres, elle sortait en `triathlon` :
    elle s'affichait « Triathlon » et **survivait** au filtre `federal_only=true`,
    l'inverse du besoin de disciplines (#76). Le titre d'épreuve nomme ici un
    sport : l'événement n'a pas à s'y substituer.
    """
    resultats = oktime._course_results(
        _course_simple(title_course), url=URL_48555,
        evenement_title="Triathlon de Lacanau 2026",
    )

    assert resultats[0].event_type == attendu


def test_course_results_taille_de_lepreuve_prime_sur_celle_de_levenement():
    """« Format S » dans un « Triathlon L de Mimizan » est un S : le titre
    d'événement ne sert qu'à nommer le sport, jamais à dicter la taille."""
    resultats = oktime._course_results(
        _course_simple("Format S"), url=URL_48555,
        evenement_title="Triathlon L de Mimizan",
    )

    assert resultats[0].event_type == "triathlon-s"


def test_course_results_concatenation_reste_correcte_si_les_titres_se_contredisent():
    """« Aquathlon 10 13 ans » dans « Triathlon de Lacanau » sort bien en aquathlon."""
    course = {
        "title_course": "Aquathlon 10 13 ans",
        "epreuve_id": 1,
        "date_course": "02/05/2026",
        "distance_course": "2,000",
        "status": "finish",
        "runners": [{"nom": "Lou BERNARD", "temps_finish": "00:12:00"}],
    }

    resultats = oktime._course_results(
        course, url=URL_48555, evenement_title="Triathlon de Lacanau 2026"
    )

    assert resultats[0].event_type == "aquathlon"


def test_course_results_date_et_distance():
    resultats = _courses(LACANAU, 0)

    assert all(r.event_date == date(2026, 5, 2) for r in resultats)
    assert all(r.distance_km == 110.0 for r in resultats)


def test_course_results_relais_uniforme_sur_la_course():
    """Décider par course garantit que `Course.is_relay` et
    `Participation.is_relay` ne divergent pas selon l'ordre des participants."""
    assert all(r.is_relay for r in _courses(LACANAU, 1))
    assert not any(r.is_relay for r in _courses(LACANAU, 0))


def test_course_results_statuts_de_la_source():
    individuel = _courses(LACANAU, 0)
    relais = _courses(LACANAU, 1)

    assert individuel[0].status == ""      # finisher laissé à l'heuristique
    assert individuel[2].status == "DNS"   # pris_depart="N" ET abandon="O"
    assert relais[0].status == "DSQ"


def test_course_results_ecarte_une_liste_dengages(caplog):
    """`status != "finish"` **et** aucun temps : épreuve inscrite mais pas courue.
    Les importer créerait des participations sans temps, que l'heuristique du
    projet classerait DNF."""
    with caplog.at_level(logging.INFO, logger="app.scrapers.oktime"):
        resultats = _courses(ENGAGES, 0)

    assert resultats == []
    assert "liste d'engagés" in caplog.text


def test_course_results_course_enfants_non_chronometree_est_finisher():
    """`status="finish"` sans aucun temps : courue et déclarée terminée. La double
    condition l'épargne de l'écartement, et le statut explicite lui évite le DNF
    collectif."""
    resultats = _courses(ENGAGES, 1)

    assert len(resultats) == 1
    assert resultats[0].status == "finisher"
    assert resultats[0].total_time == ""


COURSE_EN_COURS = {
    "title_course": "Triathlon M Individuel",
    "epreuve_id": 60201,
    "date_course": "12/07/2026",
    "distance_course": "51,500",
    "heuredebut_course": "09:00:00",
    "reference_epreuve": "LAC26-M",
    "status": "live",
    "runners": [
        {
            "nom": "Paul MARTIN",
            "sexe": "M",
            "dossard": 12,
            "club": "",
            "categorie": "Senior",
            "temps_finish": "00:00:00",
            "classement_general": 0,
            "classement_categorie": 0,
            "classement_sexe": 0,
            "rgpd": "O",
            "abandon": "N",
            "disqualifie": "N",
            "pris_depart": "O",
            "points_de_passage": [
                {"id": "11|1", "nom": "NATATION", "time": "00:23:56"},
                {"id": "12|2", "nom": "VELO", "time": "01:40:10"},
            ],
        }
    ],
}


def test_course_results_course_en_cours_avec_points_de_passage_nest_pas_ecartee(caplog):
    """Une course en cours n'est **pas** une liste d'engagés.

    Ses participants n'ont pas encore de `temps_finish`, mais leurs
    `points_de_passage` sont renseignés : les écarter rendrait un import vide et
    **sans erreur**, et — aucune `Participation` n'étant créée — le TTL de cache
    « course en cours » (10 min) ne pourrait jamais s'armer. La course resterait
    absente jusqu'à ce que l'organisateur bascule `status` sur « finish ».
    """
    with caplog.at_level(logging.INFO, logger="app.scrapers.oktime"):
        resultats = oktime._course_results(
            COURSE_EN_COURS, url=URL_48555, evenement_title="Triathlon du Lac 2026"
        )

    assert len(resultats) == 1
    assert "liste d'engagés" not in caplog.text
    assert resultats[0].segments == [("NATATION", "00:23:56"), ("VELO", "01:16:14")]


def test_course_results_course_en_cours_ne_sort_pas_en_finisher():
    """Le repli `finisher` vise les courses **déclarées terminées** et non
    chronométrées (les courses d'enfants). Une course encore en cours n'en est
    pas une : ses partants ne sont pas arrivés, l'heuristique doit trancher."""
    resultats = oktime._course_results(
        COURSE_EN_COURS, url=URL_48555, evenement_title="Triathlon du Lac 2026"
    )

    assert resultats[0].status == ""
    assert resultats[0].total_time == ""


def test_course_results_invariants_de_course_calcules_une_seule_fois(monkeypatch):
    """Cinq invariants par course, pas par participant.

    `_is_relay_course` parcourt tous les `runners` : le recalculer à chaque
    participant rend `_course_results` **quadratique**. Mesuré en re-revue
    (2026-07-27, la mesure la plus récente et la plus complète) à 500 / 1 000 /
    2 000 participants : 0,060 / 0,196 / 0,706 s avant correction, contre
    0,010 / 0,016 / 0,035 s après — la valeur absolue dépend de la machine, ce
    qui compte est l'ordre de grandeur et le passage de quadratique à linéaire.
    Le gros du coût tombait sur les plus grosses courses du panel, celles de
    Mimizan, l'épreuve la plus fournie (1 336 participations toutes courses
    confondues, cf. design §1.1).
    """
    appels: list[str] = []
    vrai_relais, vrai_type = oktime._is_relay_course, oktime.classify_event_type
    monkeypatch.setattr(
        oktime, "_is_relay_course",
        lambda titre, runners: appels.append("relais") or vrai_relais(titre, runners),
    )
    monkeypatch.setattr(
        oktime, "classify_event_type",
        lambda texte, **kw: appels.append("type") or vrai_type(texte, **kw),
    )
    course = {
        "title_course": "Triathlon M",
        "epreuve_id": 1,
        "date_course": "01/06/2025",
        "distance_course": "51,500",
        "status": "finish",
        "runners": [
            {"nom": f"Paul MARTIN{i}", "temps_finish": "02:00:00"} for i in range(5)
        ],
    }

    resultats = oktime._course_results(
        course, url=URL_48555, evenement_title="Triathlon de Mimizan"
    )

    assert len(resultats) == 5
    assert appels.count("relais") == 1
    assert appels.count("type") == 1


def test_course_results_log_agrege_des_cumuls_conserves(caplog):
    """Une ligne par épreuve, pas une par participation."""
    course = {
        "title_course": "Triathlon M",
        "epreuve_id": 1,
        "date_course": "01/06/2025",
        "distance_course": "51,500",
        "status": "finish",
        "runners": [
            {
                "nom": f"Paul MARTIN{i}",
                "temps_finish": "02:00:00",
                "points_de_passage": [
                    {"id": "1|1", "nom": "VELO", "time": "01:30:46"},
                    {"id": "2|2", "nom": "T2", "time": "01:30:19"},
                ],
            }
            for i in range(3)
        ],
    }

    with caplog.at_level(logging.WARNING, logger="app.scrapers.oktime"):
        oktime._course_results(course, url=URL_48555, evenement_title="Triathlon de Mimizan")

    messages = [r for r in caplog.records if "décroissants" in r.getMessage()]
    assert len(messages) == 1
    assert "3 participation" in messages[0].getMessage()


# --------------------------------------------------------------------------- #
# scrape_event_all
# --------------------------------------------------------------------------- #

def _client_factice(monkeypatch, pages=None, defaut=None):
    client = FakeClient(pages if pages is not None else {"/results": LACANAU}, defaut)
    monkeypatch.setattr(oktime.httpx, "Client", lambda *a, **k: client)
    return client


def test_scrape_event_all_un_seul_appel_pour_tout_levenement(monkeypatch):
    """L'API n'a pas de route par épreuve : un GET rend l'événement entier."""
    client = _client_factice(monkeypatch)

    resultats = oktime.scrape_event_all(URL_48555)

    assert client.calls == [
        "https://ok-time.fr/wp-json/gmcap/v1/evenements/48555/results"
    ]
    assert len(resultats) == 4  # 3 participants + 1 relais


def test_scrape_event_all_importe_toutes_les_epreuves(monkeypatch):
    _client_factice(monkeypatch)

    resultats = oktime.scrape_event_all(URL_48555)

    assert {r.event_name for r in resultats} == {
        "Triathlon de Lacanau 2026 – Samedi 02 mai - Triathlon L Individuel",
        "Triathlon de Lacanau 2026 – Samedi 02 mai - Relais L & Duo",
    }


def test_scrape_event_all_ignore_le_segment_race(monkeypatch):
    """L'URL du Sheet pointe une épreuve ; l'API rend quand même l'événement."""
    client = _client_factice(monkeypatch)

    resultats = oktime.scrape_event_all("https://classement.ok-time.fr/48555/race/59697")

    assert len(client.calls) == 1
    assert len(resultats) == 4


def test_scrape_event_all_source_url_est_lurl_demandee(monkeypatch):
    """`source_url` sert de clé de cache TTL : toutes les Course partagent celle
    du Sheet, pas une URL reconstruite."""
    _client_factice(monkeypatch)
    url = "https://classement.ok-time.fr/48555/race/59697"

    resultats = oktime.scrape_event_all(url)

    assert {r.source_url for r in resultats} == {url}


def test_scrape_event_all_resout_le_slug_avant_lapi(monkeypatch):
    """Forme éditoriale : 1 GET HTML pour l'id, puis l'appel API."""
    client = _client_factice(
        monkeypatch, pages={"/evenement/": PAGE_EVENEMENT, "/results": LACANAU}
    )

    resultats = oktime.scrape_event_all(
        "https://ok-time.fr/evenement/triathlon-de-lacanau-2026/"
    )

    assert client.calls == [
        "https://ok-time.fr/evenement/triathlon-de-lacanau-2026/",
        "https://ok-time.fr/wp-json/gmcap/v1/evenements/48555/results",
    ]
    assert len(resultats) == 4


def test_scrape_event_all_ecarte_les_listes_dengages(monkeypatch):
    """L'événement ne rend que la course enfants ; la liste d'engagés est écartée."""
    _client_factice(monkeypatch, pages={"/results": ENGAGES})

    resultats = oktime.scrape_event_all("https://classement.ok-time.fr/48999")

    assert len(resultats) == 1
    assert resultats[0].event_name.endswith("Course des enfants UNICEF")


def test_scrape_event_all_url_obsolete_leve_avant_toute_requete(monkeypatch):
    client = _client_factice(monkeypatch)

    with pytest.raises(ValueError, match="obsolète"):
        oktime.scrape_event_all("https://ok-time.fr/course/triathlon-l/")

    assert client.calls == []


def test_scrape_event_all_evenement_sans_epreuve(monkeypatch):
    """Charge valide mais `data` vide : liste vide, sans exception."""
    _client_factice(
        monkeypatch,
        pages={"/results": {"success": True, "evenement_title": "X", "count": 0, "data": []}},
    )

    assert oktime.scrape_event_all(URL_48555) == []
