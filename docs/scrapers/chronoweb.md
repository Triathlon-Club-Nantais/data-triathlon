# chronoweb.com (issue #55)

`chronoweb.com` (issue #55) est du **HTML statique** dont une seule requête rend
l'**événement entier** — toutes les épreuves, classements complets, sans
pagination ni JavaScript : `epreuve`, `cat` et `point` ne sont que des paramètres
d'affichage que le navigateur traduit en bascule de classe CSS. Le fait
structurant n'est pas le markup, régulier sur les 89 épreuves du panel, mais sa
**sémantique** : une ligne du tableau est le **passage** d'un concurrent à un
point de chronométrage, pas un participant. Les compter pour des participants
triplerait l'effectif d'un triathlon (2 517 lignes pour 854 inscrits à Oléron
2024). Les lignes sont donc regroupées par `(épreuve, dossard)`.

Temps total et rangs (général **et** catégorie) viennent du **seul point final**
de l'épreuve, défini comme son `data-point` maximal — jamais du dernier point
franchi par le participant, sans quoi un abandon hériterait du temps et du rang
d'un point intermédiaire. Un concurrent absent du point final sort **sans aucun
rang** (1,42 % du panel) : promu en rang de classement, son rang intermédiaire
doublonnerait celui d'un finisher et ferait ressortir toute l'épreuve
`is_reliable=false`. Ces rangs restent lisibles dans `raw_data["points"]`, avec
vitesses et gains de place. **Le rang ne se lit pas au texte** de la cellule de
classement : elle superpose le rang général et un rang de catégorie `hidden`, et
`get_text()` y rend « 11 » pour un 1ᵉʳ/1ᵉʳ, « 11837 » pour un 118ᵉ/37ᵉ.

Les **transitions ne sont pas publiées** mais se calculent
(`cumul − intervalle − cumul précédent`, jamais négatif sur 17 497 écarts, égal
au caractère près au « Changement » de la fiche individuelle). Elles sont
renseignées partout où elles sont déductibles ; **une valeur nulle n'est pas
enregistrée**, et une transition dont un point encadrant manque ne s'invente pas.
Corollaire mesuré le 2026-07-30 : l'aquathlon relais à 8 points de la Verrerie
sort à **8 segments et non 15** — ses 14 équipes ont toutes des écarts nuls, ses
points de chronométrage étant contigus. Le remplissage suit le **motif** de
points (`_POINT_PATTERNS`, 5 motifs mesurés), jamais le type d'épreuve classé :
motif reconnu → les 5 slots positionnels, que `build_splits` ré-étiquette par
discipline ; motif inconnu → `segments` sous les libellés de la source, sans
plafond, transitions intercalées sous « Changement ».

Plafond de **2 requêtes** par import : le classement, puis le catalogue
`/resultats.php` (170 Ko) pour la commune — plus juste que celle déduite du nom
d'épreuve (« St Georges d'Oléron » contre « Oléron »), rangée en
`raw_data["city"]`, tout échec étant journalisé et ignoré. **Aucune mémoïsation**
de cette requête : `PROVIDERS` tient des singletons de module, un cache
d'instance serait un cache de processus. La **fiche individuelle** n'est jamais
requêtée (elle est cassée à la source sur les épreuves mono-point).

L'URL est canonicalisée par **allowlist** du seul paramètre `event` — la fiche
individuelle (2 des 5 URLs chronoweb du Sheet) est donc tronquée vers son
événement, et les 4 graphies d'Oléron 2024 se réduisent à une. Comme pour
runnerbreizh, cela fixe le `source_url` des `ScrapedResult`, **pas**
`Course.source_url`. Une URL sans `event` (l'archive ZIP du Sheet) est refusée
**avant tout appel réseau**, avec un message français nommant la forme attendue :
le scraper ne doit jamais tenter de parser un binaire. Deux échecs à ne pas
confondre : **pas de `h2.name` → événement introuvable, on lève** ; `h2.name`
présent mais zéro ligne → **événement sans classement publié**, import vide sans
erreur.

Trois absences, toutes de la source : **aucun club** (ces participations sont
donc hors du périmètre `scope=club`), **aucune date de naissance** — le genre se
lit sur la catégorie, dont les deux conventions cohabitent (`MSE` préfixé, `SEM`
suffixé, et `M0F` féminin malgré son `M` initial) et dont les codes d'équipe
(`MIXT`, `DUOX`, `DUOM`, `DUOF`) n'en donnent aucun —, et **aucune distinction
DNS / DSQ**. Une épreuve est marquée relais par son **libellé** (`relais`, `duo`,
`team`), jamais par la catégorie : `MASC`, `FEM` et `MIXT` servent aussi de
catégories « toutes classes » en individuel. Sur une épreuve relais, le libellé
de la colonne Nom est enregistré **entier** comme nom, sans prénom — le découpage
des individus mutile 52 des 707 équipes du panel. Les limites du classifieur
partagé mises en évidence par le sondage (« 53 km » d'un trail classé
`course-a-pied`, épreuve sans sport nommé repliée sur `triathlon`) sont **hors
périmètre** : elles affectent tous les fournisseurs.

Sondage du HTML réel (fait autorité) :
`docs/superpowers/specs/2026-07-29-chronoweb-sondage.md`. Spec, plan et tâches :
`specs/005-chronoweb-scraper/`.
