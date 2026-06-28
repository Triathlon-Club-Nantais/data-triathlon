"""
Moteur partagé pour la plateforme Klikego / Breizh Chrono.

Les deux fournisseurs utilisent le même back-office. Leur page de résultats
charge l'intégralité de la liste (finishers + DNF/DNS/DSQ) dans une iframe
`/bc/resultats/course-result.jsp` qui embarque les données dans un
`<script id="data">` encodé base64 + XOR (clé 'K'). C'est la source de vérité,
contrairement à `/v8/evenement/resultats-search.jsp` qui n'expose que les
classés et sous-pagine.

Format d'une ligne (séparateur `|`), 12 champs :
  dossard|diploma|classement|classementCat|nom|cat|sexe|club_ou_ville|inter|officiel|reel|endurance
"""
import base64

from bs4 import BeautifulSoup

_XOR_KEY = ord("K")


def decode_data_block(html: str) -> list[list[str]]:
    """Décode le `<script id="data">` d'une page course-result.jsp.

    Retourne une liste de lignes, chaque ligne = liste de ses champs (str).
    `[]` si le bloc est absent ou vide.
    """
    el = BeautifulSoup(html, "lxml").find(id="data")
    if not el:
        return []
    raw_b64 = el.get_text().strip()
    if not raw_b64:
        return []
    raw = base64.b64decode(raw_b64)
    text = bytes(b ^ _XOR_KEY for b in raw).decode("utf-8")
    return [line.split("|") for line in text.split("\n") if line.strip()]
