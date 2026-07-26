"""
Tests unitaires pour scrapers/oktime.py (sans réseau).

Les fixtures sont des charges API réduites, calquées sur le schéma mesuré au
panel du 2026-07-26 (cf. docs/superpowers/specs/2026-07-26-oktime-scraper-design.md).
Le schéma réel est revérifié par le test `integration` sur l'événement 48555.
"""
import json
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
    """Réponse HTTP factice, texte + JSON."""

    def __init__(self, contenu, status_code: int = 200):
        self.status_code = status_code
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
        for motif, reponse in self.pages.items():
            if motif in url:
                return reponse if isinstance(reponse, FakeResponse) else FakeResponse(reponse)
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
