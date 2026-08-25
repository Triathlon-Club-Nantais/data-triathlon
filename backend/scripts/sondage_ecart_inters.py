"""Re-sonde la règle d'écart des inters **contre le module livré** (#486, T050).

Le sondage initial (`docs/superpowers/specs/2026-08-25-ecart-inters-total-sondage.md`)
mesurait 0 ligne signalée sur 4 150 — mais sur un prototype jetable, pas sur
`app/services/split_gap.py`. Ce script referme l'écart : il importe le module réel et
rejoue la mesure, pour que le chiffre qui porte tout le lot soit rattaché au code.

C'est lui qui a révélé que le prototype réimplémentait — et déformait — le gabarit de
segments. Ne pas y réintroduire de constante locale : les seuils viennent du module,
faute de quoi le script validerait une règle que le produit n'applique plus.

    uv run python scripts/sondage_ecart_inters.py [chemin/vers/base.db]

Lecture seule. Sortie parsable ligne à ligne, code de sortie 1 si le taux de
signalement dépasse le plafond attendu.
"""
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import split_gap  # noqa: E402

#: Au-delà, la règle n'est plus un signal mais du bruit — le seuil de 2 % de
#: l'audit en signalait 8,02 %.
TAUX_MAX = 0.005


def main(chemin: str) -> int:
    db = sqlite3.connect(f"file:{chemin}?mode=ro", uri=True)
    lignes = db.execute(
        "select p.id, p.total_time, p.splits, c.id, c.event_type, c.is_relay "
        "from participations p join courses c on c.id = p.course_id"
    ).fetchall()

    ecarts_par_course: dict[int, list[float]] = defaultdict(list)
    evaluees = []

    for pid, total_time, raw_splits, course_id, event_type, is_relay in lignes:
        ecart = split_gap.gap(
            total_time,
            json.loads(raw_splits) if raw_splits else None,
            event_type=event_type,
            is_relay=bool(is_relay),
        )
        if ecart is None:
            continue
        ecarts_par_course[course_id].append(ecart)
        evaluees.append((pid, course_id, ecart, split_gap.parse_duration(total_time)))

    medianes = {cid: split_gap.median(valeurs) for cid, valeurs in ecarts_par_course.items()}

    signalees = [
        (pid, course_id, ecart)
        for pid, course_id, ecart, secondes in evaluees
        if split_gap.is_outlier(
            ecart,
            median=medianes[course_id],
            evaluated_rows=len(ecarts_par_course[course_id]),
            total_seconds=secondes,
        )
    ]

    epreuves_marquees = [
        (cid, mediane)
        for cid, mediane in medianes.items()
        if mediane is not None and abs(mediane) > split_gap.EVENT_GAP_RATIO
    ]

    print(f"lignes                : {len(lignes)}")
    print(f"lignes evaluables     : {len(evaluees)}")
    print(f"epreuves evaluables   : {len(ecarts_par_course)}")
    print(f"epreuves marquees     : {len(epreuves_marquees)}")
    print(f"lignes signalees      : {len(signalees)}")

    if not evaluees:
        print("verdict               : rien a mesurer")
        return 0

    taux = len(signalees) / len(evaluees)
    print(f"taux de signalement   : {100 * taux:.3f} %")

    for pid, course_id, ecart in signalees[:20]:
        print(f"  signalee p{pid} c{course_id} ecart={100 * ecart:+.1f}%")

    if taux > TAUX_MAX:
        print(f"verdict               : ECHEC — au-dela du plafond de {100 * TAUX_MAX:.1f} %")
        return 1
    print("verdict               : OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "triathlon.db"))
