# Batch backlog B (2026-10-06) : design

Issues : #1186, #1193, #1191, #1212, #1206, #1202, #1209. Une PR parapluie.
Ordre d'exécution : #1186, #1193, #1191, #1212, #1206 + #1202, #1209. Le
refactor passe d'abord pour que #1209 s'écrive dans les nouveaux modules.

## 1. #1186 Découpage d'`import_service`

État mesuré : `import_service.py` fait 2201 lignes en trois groupes qui ne
s'appellent que dans un sens (orchestration vers dispatch, orchestration vers
persistance ; dispatch et persistance ne se connaissent pas).

- `services/import_dispatch.py` : `validate_url`, `merge_cached_courses`,
  `fanout_counters`, `make_cache_probe`, `scrape_all`, `scrape_all_streaming`,
  `importable`, `require_event_name`, `cached_result`, et la référence
  `registry_scrape_event_all` / `SessionLocal` qu'ils lisent.
- `services/import_persistence.py` : `Reassignment`, `PassiveSource`, les
  helpers de ligne, `_Persister`, les passes de lot (`_prepare_batch` et ses
  cinq passes), `persist_steps`, `persist_results`.
- `services/import_service.py` garde `import_event`, `iter_import_event`,
  `_confirm_committed`, `_lock_url_and_recheck_cache`. Ce qu'il appelle chez
  les deux autres devient public (règle #937, `test_service_boundaries.py`).
- `services/course_rescrape_service.py` reçoit d'`admin_actions` :
  `iter_rescrape_course`, `iter_switch_course_source`, `delete_course_source`
  et leurs helpers privés. `course_or_404`, `instantane`, `CHAMPS_COURSE`
  deviennent publics dans `admin_actions`. (`rescrape_service` existe déjà :
  c'est le rescrape de masse CLI.)
- Aucun réexport de compatibilité. Imports, routers et `monkeypatch` des tests
  visent le module qui définit le symbole. Les ~25 patches de
  `registry_scrape_event_all` sont repointés et un test garde-fou vérifie que
  le patch prend effet (sinon le scrape réel passerait inaperçu).
- `test_no_caller_instantiates_the_persister_outside_import_service` vise le
  nouveau module de rescrape.
- `backend/AGENTS.md` : inventaire des modules et paragraphe « Cache TTL ».

Critère : suite unitaire verte sans changement de comportement.

## 2. #1193 Date de course contredite par l'année de l'événement

Mesure (prod, 06/10) : épreuve 1047, Sportinnovation
`Evenements/Resultats/6450`, nom « Bayman - Triathlon du Mont Saint-Michel
2024 - Triathlon L », date 2026-10-10. La page détail de la course publie
`Triathlon L (10/10/2026)` alors que la course M du même événement (6433)
publie `06/10/2024`. Erreur de la source, recopiée telle quelle.

Règle (Sportinnovation, voie legacy `scrape_event_all`) : quand le titre
d'événement porte une année à quatre chiffres et que la date d'une course est
d'une autre année, cette date est écartée ; la course prend la date d'une
course sœur dont l'année concorde (la plus fréquente), sinon `None`. Journalisé
en warning. Test sur fixtures HTML figées. La correction de 1047 en prod passe
par un rescrape après déploiement (session prod).

## 3. #1191 Hydratation #418 sur la fiche épreuve

1. Reproduire en `next dev` (messages non minifiés) sur une fiche épreuve en
   session admin, backend local ; capturer le nœud en écart.
2. Corriger la cause trouvée, avec un test.
3. Sans reproduction locale : suspect n°1 corrigé (lecture brute de
   `useSession()` dans `AppNav` et `UserMenu`, hors `useHydratedSession`, le
   cas de #1090), et la PR dit `Refs #1191` ; la fermeture attend la recette prod.

## 4. #1212 Meilleur classement relatif

Fiche athlète : une tuile « Meilleur classement » remplace « Meilleure place »
et « Meilleur ratio ». Valeur « 3e », détail « sur 850 · Top 1 % ». Le résultat
retenu est celui de meilleur centile `rank_overall / course_finishers`
(`rankRatio`, qui écarte déjà les résultats non fiables et les épreuves de
moins de 2 finishers) ; à défaut de dénominateur, meilleur rang brut sans
« sur N ». Relais exclus comme aujourd'hui. Compteurs club inchangés. Front
seulement (`course_finishers` est déjà servi).

## 5. #1206 + #1202 Règle de comptage TCN stockée

### Colonne et règle

`participations.counts_for_tcn` (bool, non nul, défaut faux, indexé). Une seule
définition, SQL, dans un repository (`tcn_count_repository` ou
`participation_repository`), qui recalcule la colonne pour un ensemble de
courses, d'athlètes ou tout, puis `Course.tcn_count` depuis la colonne.

Un résultat compte si l'une des conditions tient :

1. son libellé normalisé est dans la portée et l'entrée n'est pas ambiguë ;
2. son athlète, ou un de ses équipiers (`participation_teammates`), est un
   licencié rattaché pour `season_of(course.event_date)` ;
3. son libellé est dans la portée mais ambigu, et l'athlète est rattaché au
   club par ailleurs : un autre résultat sous un libellé non ambigu de la
   portée, ou une licence rattachée quelle que soit la saison.

Lecteurs repointés sur la colonne : tous les `tcn_clause(Participation.club)`
des repositories, `ParticipationOut.is_tcn` (lit le champ ORM), `stats_service`
(`course_summary`), `admin_actions.adjust_counts`, `opposition_service`,
`recompute_tcn_counts_all`. `tcn_clause` sur `Athlete.club` (recherche,
effectif, composition, revue d'identité) et `is_tcn` des scrapers (choix des
pages détail) restent sur le libellé : hors périmètre, issue de suite.

Déclencheurs de recalcul : fin d'import (courses importées), écriture de la
portée (tout), synchro ou import de membres (tout), réattachement, fusion,
séparation, équipiers (athlètes touchés : la condition 3 dépend des autres
résultats de l'athlète). Migration : ajout de la colonne, backfill avec la
règle, `tcn` marqué ambigu.

### Libellés ambigus (#1206)

`counter_scope_entries.ambiguous` (bool, défaut faux). Bascule dans
`/admin/portee-compteurs` (`PATCH /admin/counter-scope/{kind}/{id}`), avec
recalcul. Le registre en mémoire n'en a plus besoin pour le comptage.

### Licenciés par saison (#1202)

Table `club_members` : `id`, `season` (année de début, convention
`core/season`), `licence_id` (nullable), `nom`, `prenom`, `gender`,
`last_name_key`, `first_name_key`, `athlete_id` (FK nullable, `SET NULL`),
`link_status` (`auto`, `manual`, `unlinked`, `ambiguous`), `source` (`fftri`,
`file`), `created_at`. Unicité `(season, licence_id)` quand la licence existe,
`(season, last_name_key, first_name_key)` sinon.

Correspondance de saison : la licence FFTri « 2027 » vue en octobre 2026 couvre
septembre 2026 à août 2027, soit `season = 2026` ; seule cette saison compte
(choix utilisateur).

Rattachement : clé d'identité sur une fiche principale ou une variante
(`athlete_aliases`) ; zéro ou plusieurs candidates (homonymes de rang ≥ 1) →
non rattaché ou ambigu, en revue. Un rattachement manuel survit aux synchros.

Sources :

- `sync-club-members` (CLI de batch) et bouton admin : lit le JSON-LD
  (`SportsTeam.member[]` : `name` « NOM Prénom », `gender`, `identifier`) de
  `https://fftri.t2area.com/clubs/triathlon-club-nantais.html` via
  `core/http`, saison lue sur la page ; remplace la liste de la saison en
  gardant les rattachements manuels.
- Import CSV/XLSX pour une saison passée choisie (`sheet_source.read_table`,
  2 Mo) : colonnes nom, prénom, sexe et licence optionnels ; remplace la saison.

Écran `/admin/membres` : saison, compteurs, non rattachés et ambigus avec
« Rattacher à une fiche » (`AthleteSearchPicker`), « Relire la liste FFTri »,
import de fichier. Permission `club_members:manage`.

RGPD : avenant à `2026-10-01-base-legale-decision.md` (traitement, intérêt
légitime, données publiées par la FFTri, minimisation, conservation fin de
saison + une saison, purge par `purge-retention`, levier « ciblage des seuls
adhérents » réexaminé) ; politique de confidentialité mise à jour avec son
`updatedAt` dans le même commit.

## 6. #1209 Homonymes fusionnés

Table `athlete_known_clubs (athlete_id, club_key)` : clubs confirmés par un
admin, en clé canonique (`normalize_club` puis alias de club).

Club significatif : non vide, pas une ville au format « nom (code postal) »,
hors portée TCN.

- **Séparation** : `POST /admin/athletes/{id}/detach {participation_ids}`
  (`athletes:write` + `participations:reassign`). Crée l'homonyme
  (`create_homonym`, mêmes nom/prénom/sexe, club du dernier résultat déplacé),
  réattache chaque résultat (verrou `athlete_locked`, refus si conflit sur une
  course), enregistre la paire ignorée (pas de refusion par
  `reconcile-athletes`), audit `athlete.detach`, recalcul de `counts_for_tcn`.
  Front : sélection de résultats sur la fiche athlète (admin), bouton
  « Séparer vers une nouvelle fiche », `DangerConfirm`.
- **Revue** : motif `multi_club` dans `/admin/identites` : fiche dont les
  résultats individuels validés portent au moins deux clubs significatifs
  canoniques distincts non confirmés. Gestes : séparer (lien vers la fiche),
  ou « Confirmer ce club pour cette fiche » (`athlete_known_clubs`).
  `review_details` sélectionne `Participation.club`.
- **Import** (`_resolve_pending`) : clé résolue sur une fiche principale P qui
  est une fiche de membre TCN (un résultat `counts_for_tcn` ou une licence
  rattachée), résultat portant un club significatif absent des clubs des
  résultats de P et de ses clubs confirmés → homonyme de même clé portant ce
  club (dans ses résultats ou confirmé), sinon nouvel homonyme, paire ignorée,
  entrée `homonyms_created`. Club vide, ville, libellé de la portée : rattaché
  à P comme aujourd'hui.

## Tests et livraison

TDD pour chaque partie (pytest, vitest). Une migration Alembic par changement
de modèle, vérifiée par `test_migrations.py`. Doc : `docs/api/admin-donnees.md`
(séparation, revue), `backend/app/cli/AGENTS.md` (`sync-club-members`),
`backend/app/models/AGENTS.md`. Fin de branche : revue de code, puis
`ui-ux-review`. PR parapluie : `Closes` #1186 #1193 #1212 #1206 #1202 #1209,
#1191 selon la reproduction.
