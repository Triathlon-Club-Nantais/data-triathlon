# Phase 0 — Recherche : la page épreuve (lot #486)

Six inconnues bloquaient le plan. Cinq sont tranchées par lecture du code, une par mesure
sur les données réelles.

---

## R1 — Le seuil de signalement des temps douteux

**Décision** : abandonner le seuil de 2 % proposé par l'audit. Dédoubler le signal —
**niveau épreuve** quand la médiane des écarts dépasse 1 % (le chronométreur ne publie pas
un segment), **niveau ligne** quand l'écart d'une ligne s'éloigne de la médiane de son
épreuve de plus de 5 %, sur les épreuves d'au moins 10 lignes évaluables et pour au moins
60 s d'écart.

**Rationale** : mesuré sur les 4 150 lignes évaluables de `backend/triathlon.db`, le seuil
de 2 % signale **333 lignes (8,02 %)**, dont **285 sur la seule course 47**, que le produit
tient par ailleurs pour fiable. La distribution des écarts est bimodale — médiane 3 s,
p75 4 s, puis saut à 143 s au p90 —, et 81,7 % des écarts sont « total > somme », signature
d'un segment non publié plutôt que d'une ligne fausse. La règle retenue signale **0 ligne
sur 4 150**, et le cas cible de l'audit (course 214, 69,3 % d'écart) la passe largement.

**Alternatives rejetées** :
- *Seuil relatif seul, quelle que soit sa valeur* — la bimodalité interdit un curseur :
  entre 5 % et 2 %, le taux saute de 0,53 % à 8,02 %.
- *Seuil relatif + plancher en secondes* — mesuré aussi : ne discrimine pas, le taux
  bascule de 4,5 % à 0 % entre un plancher de 300 s et 600 s.
- *Signal au seul niveau ligne* — répéterait treize fois, sur treize lignes, que la
  transition d'un aquathlon n'est pas publiée.

**Point de vérité** : `docs/superpowers/specs/2026-08-25-ecart-inters-total-sondage.md`.
Il prime sur cette spec et sur ce plan.

---

## R2 — Où calculer l'écart, et où calculer la médiane

**Décision** : les deux côté **backend**, dans `app/services/stats_service.py`. Le serveur
publie l'écart par ligne (`ParticipationOut.split_gap_ratio`) et la médiane par épreuve
(`CourseSummary.split_gap_median`). Le front ne fait que comparer aux seuils d'affichage.

**Rationale** : deux contraintes convergent.
1. **La médiane est hors de portée du client.** Elle porte sur l'épreuve entière, et
   l'écran ne reçoit que vingt lignes ; la calculer sur la tranche la ferait varier de page
   en page. `stats_service.course_summary` lit déjà toutes les lignes via
   `participation_repository.summary_rows_for_course`, `splits` et `total_time` compris —
   le coût marginal est nul.
2. **La règle ne peut pas vivre en deux exemplaires.** Si le front recalculait l'écart de
   chaque ligne pendant que le back calcule la médiane, les deux implémentations
   divergeraient sur le choix des segments sommés. Le Principe II l'interdit nommément, et
   #76 en est la trace : trois listes divergentes du critère club, et un `%nantais%` qui a
   compté tout Nantes comme TCN.

**Alternative rejetée** : *médiane au serveur, écart de ligne au client* — c'était le
découpage le plus économe en champs publiés, et c'est précisément le partage qui recrée le
risque de #76 : le serveur somme les clés du schéma de sport (qui vit en TypeScript dans
`frontend/lib/utils/splits.ts`), le client somme les colonnes qu'il affiche. Rien ne
garantit que ce soit le même ensemble.

**Conséquence** : le schéma de segments par sport doit exister côté Python. Il n'y est pas
aujourd'hui — `splitColumnsFromKeys` est purement frontend. C'est le seul vrai coût de ce
choix, et il est borné : cinq listes de clés, aucune logique.

---

## R3 — Le nombre de clubs distincts n'est pas publié

**Décision** : ajouter `CourseSummary.clubs_total` — le nombre de clubs **distincts**
renseignés sur l'épreuve, dénominateur du « et N autres clubs ».

**Rationale** : `CourseSummary` publie `categories_total` (« somme sur toutes les
catégories », `schemas/course.py`) mais **rien d'équivalent pour les clubs** : seulement
`clubs: list[ClubCount]`, tronquée à `_MAX_CLUBS = 9`. Sans ce champ, le pied « et N autres
clubs » n'est pas calculable — la carte ne sait pas ce qu'elle omet, ce qui est exactement
le défaut que `RES-7` reproche.

Noter l'asymétrie de sens, qui doit se retrouver dans le nommage et la documentation :
`categories_total` compte des **participants**, `clubs_total` comptera des **clubs**. Les
deux servent pourtant le même besoin — dire ce que la carte n'affiche pas.

**Alternative rejetée** : *déduire le reste de `total − Σ des clubs affichés`* — donnerait
un nombre de **participants** non listés, pas un nombre de clubs, et le pied demandé par
l'audit est « et N autres **clubs** ».

---

## R4 — La liste des épreuves ne reçoit pas la fiabilité

**Décision** : ajouter `is_reliable` et `quality_issues` à `EventOut`, alimentés dans
`_grouped_events_query`.

**Rationale** : `EventOut` (`schemas/course.py`) porte huit champs, aucun de fiabilité. La
requête agrégée groupe déjà **par `Course.id`** — donc une ligne = une épreuve, et les deux
colonnes sont fonctionnellement dépendantes de la clé primaire déjà présente dans le
`GROUP BY`. `is_reliable` est un `hybrid_property` avec expression SQL
(`coalesce(reliability_override, is_reliable_computed)`, `models/course.py:139-147`),
utilisable tel quel dans un `select`.

**Piège identifié** : `quality_issues` est une colonne `JSON`. PostgreSQL n'a **pas**
d'opérateur d'égalité sur le type `json`, donc l'ajouter au `GROUP BY` échouerait en
production tout en passant sur SQLite. Il faut l'ajouter au `SELECT` **seulement**, en
s'appuyant sur la dépendance fonctionnelle à `Course.id`. Les cinq colonnes déjà listées
dans le `GROUP BY` (`name`, `event_date`, `event_type`, `is_relay`, `distance_km`) y sont
d'ailleurs redondantes pour la même raison. Un test doit couvrir ce chemin sur les deux
moteurs, ou au minimum documenter le risque.

**Alternative rejetée** : *ne pas porter la marque dans la liste* — l'entrée `RES-10` la
nomme explicitement, et `/resultats` est l'écran le plus visité du produit.

---

## R5 — Le filtre club/catégorie sur le classement

**Décision** : deux paramètres de requête facultatifs `club` et `category` sur
`GET /courses/{course_id}`, transmis à `participation_repository.list_page_for_course`,
en **égalité exacte** sur `Participation.club` et `Participation.category`.

**Rationale** : les valeurs proposées à l'écran viennent de `summary.clubs[].name` et
`summary.categories[].name`, elles-mêmes issues d'un `Counter` sur ces deux colonnes
(`stats_service`). Ce sont donc littéralement les chaînes stockées : l'égalité exacte est
à la fois la plus simple et la seule qui garantisse que le compteur affiché corresponde au
nombre de lignes rendues. Défaut `None` = pas de filtre — Principe V (neutralité par
défaut) satisfait, et ajout purement additif à `/api/v1` — Principe IV satisfait.

`list_page_for_course` compose déjà `club_only`, `q` et la pagination par ajouts
successifs de `.filter(...)` : les deux nouveaux filtres s'y insèrent sans restructuration,
et se cumulent naturellement.

**Alternatives rejetées** :
- *Recherche partielle (`ilike`)* — « BLAIN TRIATHLON » matcherait aussi
  « BLAIN TRIATHLON JEUNES » ; le compteur de la carte et le total du classement
  divergeraient, ce qui est le défaut que `RES-9` vient de faire corriger.
- *Réutiliser `scope` pour le club* — `scope` porte la sémantique **TCN**, arbitrée par
  `app/core/club.py` (dépositaire unique, #76). La surcharger d'un club arbitraire
  détruirait cette unicité.
- *Route dédiée* — dupliquerait pagination, tri et sérialisation pour un préfixe d'URL,
  exactement l'arbitrage déjà rendu pour `unreliable` sur `GET /courses`.

---

## R6 — L'accès au libellé complet des catégories

**Décision** : une table de correspondance statique côté frontend
(`frontend/lib/categories.ts`), bornée aux codes réellement rencontrés dans les données,
rendue par un `title` **plus** un texte accessible — jamais par un `title` seul.

**Rationale** : aucune table n'existe, ni côté back (`grep` sur « PoM », « V1 » dans
`backend/app` : zéro occurrence) ni côté front (`lib/labels.ts` ne porte que le mot
« Catégorie » lui-même). C'est donc une création. La placer côté front est justifié : c'est
un libellé d'affichage, il ne conditionne aucune requête, et le mettre en base ferait une
migration pour une constante.

Le `title` HTML seul ne satisfait pas `FR-028` — il n'existe ni au doigt ni au clavier.
Le produit a déjà le patron correct : `CelluleInter` (`RaceFinishers.tsx`) combine
`role="img"`, `title` et `aria-label` pour le marqueur de split illisible posé par #472.
Le même patron sert ici, et l'aligner évite d'inventer un second motif.

**Une table plate ne suffit pas — mesuré.** La base de dev porte **123 codes distincts**
sur 11 622 lignes catégorisées, et ils relèvent d'au moins trois nomenclatures : FFTRI
(`S1`…`S4`, `V1`…`V6`, `CA`, `JU`, `MI`), un suffixe de genre accolé (`S2M`, `S2F`, `V3H`
— trois lettres différentes pour deux genres), et des familles étrangères à la FFTRI
(`M0`…`M6`, `MA1`…`MA5`, `M SENIOR`, `F VETERAN`, `REX`, `EQM`, et un `-` pour 65 lignes).

Une table de **17 codes de base + une règle de suffixe de genre** couvre **80,7 % des
lignes** (61 codes sur 123). C'est le bon rapport : la table reste lisible, et la règle de
suffixe fait le travail de 44 entrées à elle seule. Les familles restantes se traitent par
**deux règles supplémentaires** — le genre en mot préfixe (`M SENIOR`), et les séries
masters `M0`…`M6` / `MA1`…`MA5` — mesurées à ~13 points de couverture de plus. Le relevé
exact des codes à inscrire est une **requête**, pas un arbitrage : il se fait au moment
d'écrire la table.

**Alternative rejetée** : *nomenclature FFTRI complète, sans mesure* — elle produirait des
libellés faux pour des codes que le produit ne verra jamais, et raterait les 19 % de lignes
qui n'en relèvent pas. `FR-029` acte qu'un code hors table s'affiche tel quel : c'est la
seule réponse honnête pour une queue de 37 codes à 150 lignes.

---

## Ce qui reste ouvert

- **Le seuil de R1 n'est calibré que côté fausse alerte.** Zéro ligne signalée sur la base
  de dev prouve l'absence de bruit, pas la captation. À re-sonder sur la base de
  production ; d'ici là, un test unitaire fige le cas de la course 214.
- **Les codes de catégorie à couvrir en R6** se relèvent sur la base de dev au moment
  d'écrire la table, pas avant : c'est une requête, pas un arbitrage.
