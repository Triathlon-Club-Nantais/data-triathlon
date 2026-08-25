# Relevé de données — lot #486 (T001)

Ce que la base de dev contient réellement, mesuré le 2026-08-25 sur
`backend/triathlon.db` : **72 épreuves, 11 629 participations, 10 873 athlètes**.

Ce fichier est un **intrant**, pas un arbitrage : il fournit aux trois stories des cas de
test réels plutôt qu'inventés, et alimente la table de libellés de `T043`. Il ne dit rien
que la base ne dise ; s'il vieillit, il se refait.

---

## 1. Épreuves témoins

Chaque ligne a été choisie pour **un** cas d'exigence, et le vérifie sur de la vraie
donnée.

| Épreuve | Sert à vérifier | Fait mesuré |
| --- | --- | --- |
| **c27** — Triathlon de la Roche, Triathlon S | `FR-012` `FR-014` `SC-001` — la part « Autres » | 26 catégories, dont **8 affichées couvrant 70,1 %** (383/546). **29,9 % des participants n'apparaissent nulle part** — pire que les 13,9 % relevés sur la course 214 par l'audit. |
| **c23** — Triathlon de la Roche, Triathlon M | `FR-012` — second cas de troncature | 22 catégories, top 8 à **79,6 %** (465/584). |
| **c8** — Dinard, Distance Olympique | `FR-015` — le pied « et N autres clubs » | **174 clubs distincts**, 9 affichés → le pied doit dire **« et 165 autres clubs »**. |
| **c47** — Bayman, Mont Saint-Michel, Triathlon M | `FR-016` — l'en-tête masqué sur liste vide | **aucun club renseigné** sur 696 participations. C'est aussi l'épreuve que le seuil de 2 % de l'audit noircissait à 285 lignes signalées. |
| **c65** — Aquathlon des 2 amants, Course 6-9 ans | `FR-005` — le signal d'épreuve | médiane d'écart **+11,44 %** sur 9 lignes évaluables : la T1 n'est pas publiée, le schéma `aquathlon` n'en a pas. |
| **c66** — Aquathlon des 2 amants, Course 8-11 | `FR-005` `FR-006` — signal épreuve, pas ligne | médiane **+7,44 %**, et **100 % des 13 lignes** s'écartent du même ordre. Le dire treize fois serait du bruit. |
| **c8** — Dinard, Distance Olympique | `FR-005` en négatif — aucun signal | médiane d'écart **+0,07 %** sur 12 lignes : les inters collent au total. |
| **c47** | `FR-006` en négatif — aucune ligne marquée | 681 lignes évaluables, médiane +1,69 %, **0 ligne** signalée par la règle retenue. |
| **course 214** *(production, hors base de dev)* | `SC-004` — la captation | 31 s + 34 s + 19 min 18 s pour 01:06:18 → **69,3 % d'écart**. À figer en fixture (`T004`) : c'est le **seul** cas de captation dont on dispose. |

**Épreuves à médiane d'écart significative** (`|médiane| > 1 %`) : **5 sur 25** ayant des
lignes évaluables — c65 (+11,44 %), c66 (+7,44 %), c61 (+2,10 %), c47 (+1,69 %),
c63 (+1,67 %).

---

## 2. Codes de catégorie

**123 codes distincts** sur 11 622 lignes catégorisées. Ils relèvent d'au moins trois
nomenclatures, et aucune table plate ne les couvre.

### Les plus fréquents

| Code | n | Code | n | Code | n |
| --- | --- | --- | --- | --- | --- |
| `S1` | 1 004 | `S1M` | 271 | `MA1` | 87 |
| `S2` | 939 | `S3M` | 246 | `S3F` | 84 |
| `S3` | 855 | `M VETERAN` | 239 | `MA3` | 78 |
| `S4` | 766 | `S4M` | 234 | `CA` | 78 |
| `V1` | 573 | `M1` | 206 | `JuM` | 74 |
| `V2` | 538 | `M2` | 172 | `V3H` | 70 |
| `V3` | 457 | `V2M` | 168 | `CaM` | 69 |
| `V4` | 338 | `M0` | 167 | `JU` | 66 |
| `SE` | 327 | `S2F` | 164 | `-` | 65 |
| `M SENIOR` | 286 | `V1M` | 161 | `MiM` | 61 |
| `S2M` | 277 | `V5` | 154 | `PoM` | 34 |

### Les familles, et ce qu'elles impliquent pour la table

| Famille | Exemples | Traitement |
| --- | --- | --- |
| FFTRI, code nu | `S1`…`S4`, `V1`…`V6`, `SE`, `CA`, `JU`, `MI` | **table de base**, 17 entrées |
| FFTRI + suffixe de genre | `S2M`, `S2F`, `S2H`, `V3H`, `CaM`, `JuF` | **règle de suffixe** — trois lettres pour deux genres (`M`/`H` = hommes, `F` = femmes) |
| Genre en mot préfixe | `M SENIOR`, `F VETERAN`, `M JUNIOR` | **règle de préfixe** |
| Masters hors FFTRI | `M0`…`M6`, `MA1`…`MA5` | entrées dédiées |
| Équipes et relais | `REX`, `REM`, `EQX`, `EQM`, `MPM` | entrées dédiées |
| Non renseigné | `-` (65 lignes) | rendu tel quel |

**Couverture mesurée** : les 17 codes de base **plus la seule règle de suffixe** couvrent
**80,7 % des lignes** (61 codes sur 123). Les deux règles suivantes ajoutent ~13 points.

**La queue est irréductible** : 37 codes pour 150 lignes au total. `FR-029` acte qu'un code
hors table s'affiche tel quel — c'est la seule réponse honnête, et le produit a déjà ce
réflexe avec `describeQualityIssues`, qui rend un code d'anomalie inconnu plutôt que de
l'avaler.

---

## 3. Cardinalités utiles

- **1 393 clubs distincts** sur l'ensemble de la base — assez pour que le filtre `club` ait
  un sens, bien trop pour en faire une énumération fermée côté contrat.
- **123 codes de catégorie distincts**, même conclusion pour `category`.
- **4 150 lignes évaluables** pour la règle d'écart, sur 11 629 — les exclusions sont
  détaillées au § 2 de [`data-model.md`](./data-model.md).
