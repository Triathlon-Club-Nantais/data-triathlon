# Feature Specification: Page de vérification des résultats par les bénévoles

**Feature Branch**: `20260815-114258-page-validation-benevoles`

**Created**: 2026-08-15

**Status**: Draft — cadrage seul, implémentation **non commencée**, bloquée par #270 (cf. § Dépendances)

**Input**: Issue GitHub #271 « Feature - Page de vérification des résultats pas les bénévoles. » (corps + 8 commentaires, récupérés le 2026-08-15 via `gh issue view 271` et `gh api .../issues/271/comments`)

## Décisions actées *(section additionnelle à ce cadrage — trace des arbitrages produit)*

- **Mécanisme d'accès : mot de passe partagé** sur un endpoint dédié, pour les
  5-6 bénévoles, sans SSO Google individuel ni rôle RBAC individuel.
  - Fil de décision : tjarrier propose l'option « page à mot de passe » le
    2026-08-13 16:54 ; MathieuHerrmann tranche « Go 2 [mot de passe] et on
    garde le point 1 [SSO Google] sous le coude » le 2026-08-13 17:16 ; Vinzzou
    (porteur historique du besoin) confirme le 2026-08-14 09:32 : « Tres bien
    le mdp, cest le plus simple ».
  - Rationale (MathieuHerrmann, 2026-08-13 16:28) : éviter autant que possible
    un compte individuel mail+mot de passe (charge RGPD/CNIL — collecte
    d'identité, droit à l'oubli, etc.). Un mot de passe **partagé** n'a pas
    cette contrainte car il ne collecte aucune identité individuelle.
  - **Tension à consigner, non rouverte ici** : le dernier commentaire du fil
    (MathieuHerrmann, 2026-08-14 11:11 — donc *postérieur* à la confirmation de
    Vinzzou) revient sur ce choix. Il observe que le socle SSO (#114) et le
    RBAC (#115, écran `admin/droits` livré par #240) permettent déjà de
    composer un rôle sur mesure (ex. `results:validate`) sans identité
    individuelle ni les limites de révocation notées sur #169, et propose de
    lui substituer un rôle « bénévole » attribué depuis `/admin/droits` —
    concluant « À confirmer avant le cadrage ». Ce commentaire est resté sans
    réponse écrite dans le fil. Pour ce cadrage, la décision retenue reste le
    mot de passe partagé (comportement instruit explicitement pour cette
    spec) ; quiconque relit le fil doit savoir que le dernier mot écrit n'est
    pas celui qui a été retenu ici, et que cet arbitrage reste rouvrable en
    amont d'une implémentation si le porteur produit le souhaite.
- **Le fichier `Validation resultats.dc.html`** joint à l'issue (généré par
  Claude à partir de la description) est une **inspiration de layout**
  uniquement — file de validation à gauche, panneau de correction/validation à
  droite. Il ne se reprend pas tel quel comme composant ; la reconstruction
  suit les conventions de composants du front (`frontend/AGENTS.md`). Le choix
  entre la bibliothèque `components/tcn/` (identité visuelle publique) et
  `components/ui/` (primitives denses réservées au back-office) n'est **pas**
  tranché ici : `frontend/AGENTS.md` réserve `ui/` aux écrans qui ont besoin de
  la densité back-office, ce qui décrit assez bien une file + panneau
  d'édition ; mais cet écran n'est pas un écran `/admin/*` sous SSO, ce qui
  plaide pour `tcn/`. Ce point est renvoyé au plan (`/speckit-plan`), à
  trancher sur preuve (densité réelle de l'écran une fois maquetté) plutôt que
  par défaut.

## Dépendances *(à documenter, pas à résoudre dans ce cadrage)*

- **Bloquée par #270** (refonte du formulaire de saisie manuelle). #270 produit
  la dimension « en attente de validation » que cette feature consomme.
  **Vérifié dans le code au moment de ce cadrage** (2026-08-15) : sur `main`
  (dont ce worktree dérive — `git merge-base HEAD origin/main` == `HEAD`),
  `backend/app/models/participation.py` ne porte que
  `status: finisher/DNF/DNS` ; aucun champ de validation n'existe encore. Le
  champ attendu existe uniquement sur la branche **non fusionnée**
  `20260814-130052-saisie-manuelle-resultats` :
  `Participation.is_pending_validation: bool` (défaut `False`), accompagné de
  `evidence_url` (lien vers les résultats publiés, saisi par le déclarant comme
  pièce justificative) et `team_name` (résultat collectif). Cette feature ne
  peut donc pas être implémentée avant la fusion de #270, et doit consommer
  `is_pending_validation` tel que produit là-bas plutôt que réinventer un
  champ. La spec de #270 (§ Hors périmètre) renvoie explicitement à cette
  issue la file de validation, l'édition du nom d'épreuve, la réattribution à
  un athlète et l'action de validation elle-même.
- **#330** (reprise des résultats manuels déjà en base) — **fermée le
  2026-08-15, `not_planned`** : preview et production ne portent aujourd'hui
  aucun résultat `provider = "manuel"` (le projet n'est pas encore en V1),
  donc aucun stock à reprendre. Cette dépendance ne bloque plus
  l'implémentation ; la file de validation de cette feature démarrera sur un
  stock complet dès la fusion de #270.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - File d'attente et validation d'un résultat légitime (Priority: P1)

Un bénévole accède à la page de vérification protégée par mot de passe et voit
la liste des résultats saisis manuellement en attente de validation. Il
sélectionne un résultat, relit les informations saisies par le déclarant
(épreuve, athlète, temps, splits, pièce justificative), constate qu'elles sont
correctes, et valide le résultat.

**Why this priority**: C'est le chemin nominal et le plus fréquent — sans lui,
aucun résultat saisi manuellement ne devient jamais visible, ce qui neutralise
entièrement la fonctionnalité de saisie manuelle de #270.

**Independent Test**: Peut être testé seul en créant une participation avec
`is_pending_validation=true`, en la validant depuis la page, et en vérifiant
qu'elle apparaît ensuite sur la fiche de l'athlète et entre dans les agrégats
publics dont #270 l'excluait.

**Acceptance Scenarios**:

1. **Given** au moins un résultat avec `is_pending_validation=true`, **When**
   le bénévole ouvre la page de vérification, **Then** ce résultat apparaît
   dans la file, avec l'épreuve, l'athlète déclaré, le temps, les splits
   saisis et le lien vers la pièce justificative (`evidence_url`) s'il est
   renseigné.
2. **Given** un résultat sélectionné dans la file, **When** le bénévole
   déclenche l'action de validation sans autre modification, **Then**
   `is_pending_validation` passe à `false`, le résultat sort de la file, et il
   devient visible sur la fiche de l'athlète correspondant.
3. **Given** un résultat validé, **When** un visiteur consulte les agrégats
   publics (statistiques, podiums, classements, page résultats, page épreuve,
   carte) qui l'excluaient auparavant, **Then** ce résultat y apparaît
   désormais.

---

### User Story 2 - Uniformisation du nom de l'épreuve (Priority: P2)

Un bénévole constate que l'épreuve associée à un résultat en attente porte un
nom légèrement différent d'une épreuve déjà connue en base (variante de
libellé). Il corrige le nom de l'épreuve pour l'aligner sur le nom déjà en
usage, avant de valider.

**Why this priority**: Sans cette correction, une même épreuve se fragmente en
plusieurs fiches distinctes dans le catalogue, ce qui dégrade les statistiques
et la page épreuve — mais cela reste secondaire à la validation elle-même
(P1), qui peut avoir lieu sans renommage dans le cas nominal.

**Independent Test**: Peut être testé seul en éditant le nom d'une épreuve
associée à un résultat en attente et en vérifiant que la modification se
répercute (l'épreuve visée est bien celle qui existe déjà, ou celle qui vient
d'être renommée, selon le cas).

**Acceptance Scenarios**:

1. **Given** un résultat en attente associé à une épreuve nommée
   différemment d'une épreuve existante équivalente, **When** le bénévole
   édite le nom de l'épreuve depuis le panneau de correction, **Then** le nom
   est mis à jour et reste cohérent avec les contraintes d'unicité déjà
   posées sur `Course` (nom, date, type d'épreuve, relais).
2. **Given** un renommage qui ferait coïncider l'épreuve du résultat avec une
   épreuve déjà existante, **When** le bénévole valide ce renommage,
   **Then** le système signale la collision plutôt que de produire un doublon
   silencieux ou une erreur technique brute.

---

### User Story 3 - Réattribution à un autre athlète (Priority: P2)

Un bénévole constate qu'un résultat a été saisi pour le mauvais athlète (le
déclarant s'est trompé de nom, ou plusieurs profils existent pour la même
personne). Il réattribue le résultat à l'athlète correct avant de valider.

**Why this priority**: Erreur de saisie relativement rare mais avec un impact
individuel fort (le résultat doit apparaître sur la bonne fiche) ; reste
secondaire à la validation du cas nominal (P1).

**Independent Test**: Peut être testé seul en réattribuant un résultat en
attente à un autre athlète existant et en vérifiant qu'il apparaît ensuite sur
la fiche de ce second athlète et non plus sur celle d'origine, une fois
validé.

**Acceptance Scenarios**:

1. **Given** un résultat en attente attribué à un athlète A, **When** le
   bénévole le réattribue à un athlète B existant puis valide, **Then** le
   résultat apparaît sur la fiche de B et non plus sur celle de A.
2. **Given** une tentative de réattribution vers un athlète qui possède déjà
   une participation sur la même épreuve (contrainte d'unicité
   `course_id`/`bib_number` ou doublon logique), **When** le bénévole confirme
   la réattribution, **Then** le système signale le conflit plutôt que de
   produire un état incohérent.

---

### User Story 4 - Accès protégé par mot de passe partagé (Priority: P1)

Un bénévole ouvre l'URL de la page de vérification, saisit le mot de passe
partagé communiqué à l'équipe des 5-6 bénévoles, et accède à la file de
validation. Une personne qui ne connaît pas le mot de passe ne peut pas
consulter les informations saisies par les déclarants (données personnelles :
nom, club, temps).

**Why this priority**: Sans cette protection, les informations saisies
manuellement par les utilisateurs (potentiellement non encore vérifiées)
seraient exposées publiquement — préalable de sécurité à toute autre
interaction avec la page.

**Independent Test**: Peut être testé seul en vérifiant qu'un accès sans mot de
passe (ou avec un mot de passe erroné) est refusé, et qu'un accès avec le bon
mot de passe donne accès à la file.

**Acceptance Scenarios**:

1. **Given** un visiteur sans le mot de passe, **When** il tente d'accéder à
   la page ou à ses données, **Then** l'accès est refusé.
2. **Given** un bénévole muni du mot de passe correct, **When** il le saisit,
   **Then** il accède à la file de validation et à ses actions (édition,
   réattribution, validation).
3. **Given** une session de bénévole ouverte, **When** le navigateur est fermé
   ou une déconnexion explicite est demandée, **Then** l'accès à la page
   redemande le mot de passe (aucune expiration par délai d'inactivité n'est
   requise par l'issue — hypothèse par défaut documentée en § Assumptions,
   à revoir au plan si un délai précis s'avère nécessaire).

---

### Edge Cases

- Un résultat en attente dont l'épreuve associée a été supprimée entre-temps
  (concurremment) par un autre geste d'administration : la file doit rester
  cohérente plutôt que planter sur une référence orpheline.
- Deux bénévoles ouvrent la même page en parallèle et agissent sur le même
  résultat en attente (l'un valide pendant que l'autre édite) : le second
  geste doit échouer proprement plutôt que corrompre silencieusement l'état.
- Un résultat en attente sans `evidence_url` renseigné (champ optionnel côté
  #270) : le bénévole doit pouvoir quand même l'examiner et le valider sur la
  base des seules informations saisies.
- Un résultat en attente à `team_name` renseigné (résultat collectif) : la
  file doit l'afficher distinctement d'un résultat individuel.
- Tentative de réattribution vers un athlète qui n'existe pas encore en base
  (le déclarant a mal orthographié un nom nouveau) : hors du geste de
  réattribution proprement dit, qui ne porte que sur des athlètes déjà
  existants — la création d'un nouvel athlète depuis cet écran n'est pas dans
  le périmètre décrit par l'issue.
- Le stock de résultats manuels antérieurs à #270, non marqués
  `is_pending_validation` : sans objet — #330 (fermée `not_planned`) a
  confirmé qu'aucun résultat manuel n'existe en preview ni en production.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Le système DOIT protéger l'accès à la page de vérification et à
  ses données par un mot de passe partagé, distinct du mécanisme de connexion
  SSO utilisé par le back-office (`/admin/*`).
- **FR-002**: Le système DOIT présenter aux bénévoles authentifiés la liste des
  résultats saisis manuellement en attente de validation
  (`is_pending_validation = true`), avec pour chacun : l'épreuve associée,
  l'athlète déclaré, le temps total, les splits saisis, le lien vers la pièce
  justificative si renseigné, et le nom d'équipe si le résultat est collectif.
- **FR-003**: Les bénévoles DOIVENT pouvoir éditer le nom de l'épreuve associée
  à un résultat en attente, pour l'uniformiser avec une épreuve déjà connue.
- **FR-004**: Le système DOIT signaler toute collision que produirait ce
  renommage avec une épreuve déjà existante, plutôt que de créer un doublon
  silencieux.
- **FR-005**: Les bénévoles DOIVENT pouvoir réattribuer un résultat en attente
  à un autre athlète déjà existant en base.
- **FR-006**: Le système DOIT signaler tout conflit que produirait cette
  réattribution (l'athlète cible possède déjà une participation sur la même
  épreuve), plutôt que de produire un état incohérent.
- **FR-007**: Les bénévoles DOIVENT pouvoir valider un résultat en attente,
  action qui fait passer `is_pending_validation` à `false`.
- **FR-008**: Un résultat validé DOIT devenir visible sur la fiche de
  l'athlète auquel il est attribué au moment de la validation (donc, le cas
  échéant, l'athlète réattribué plutôt que le déclarant d'origine).
- **FR-009**: Un résultat validé DOIT redevenir éligible aux agrégats publics
  (statistiques, podiums, compteurs club, classements, page résultats, page
  épreuves, carte) dont la spec de #270 l'excluait tant qu'il restait en
  attente.
- **FR-010**: Le système NE DOIT PAS exposer, à un visiteur non authentifié
  par le mot de passe partagé, les informations saisies par les déclarants sur
  les résultats en attente de validation.
- **FR-011**: Le système DOIT continuer d'exclure des agrégats publics tout
  résultat qui reste `is_pending_validation = true` après une action de
  renommage d'épreuve ou de réattribution qui ne l'a pas validé.

*Hors périmètre de cette spec — cf. § Dépendances :*

- La reprise (rétro-marquage) des résultats manuels saisis avant #270 : sans
  objet, #330 a établi qu'il n'existe aucun stock à reprendre.
- La production du champ `is_pending_validation` lui-même et l'exclusion des
  agrégats publics associée : livrés par #270, pas par cette feature.
- Le choix entre mot de passe partagé et rôle RBAC individuel porté par le SSO
  existant : arbitré en amont de ce cadrage (cf. § Décisions actées) — cette
  spec ne rouvre pas ce choix, elle documente la tension relevée dans le fil
  de l'issue.

### Key Entities *(include if feature involves data)*

- **Participation (résultat)** — entité déjà normalisée par #270 ; cette
  feature en lit `is_pending_validation`, `evidence_url`, `team_name`, et
  écrit potentiellement `is_pending_validation` (validation),
  `athlete_id` (réattribution, geste indirect via l'entité Athlete visée).
- **Course (épreuve)** — cette feature écrit potentiellement le nom de
  l'épreuve associée à un résultat en attente (uniformisation).
- **Athlete (athlète)** — cette feature lit la liste des athlètes existants
  pour permettre une réattribution ; n'en crée pas de nouveau depuis cet
  écran.
- **Mot de passe partagé (accès)** — un secret unique, non individuel, gardant
  l'accès à cette page ; ne porte aucune identité de bénévole.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Un bénévole peut faire passer un résultat de « en attente » à
  « validé », de bout en bout (accès, relecture, validation), en moins de 2
  minutes dans le cas nominal (sans renommage ni réattribution).
- **SC-002**: 100 % des résultats validés depuis cette page apparaissent sur la
  fiche de l'athlète auquel ils sont finalement attribués, sans intervention
  technique supplémentaire.
- **SC-003**: 0 résultat encore marqué en attente de validation n'apparaît dans
  les agrégats publics (statistiques, podiums, classements, page résultats,
  page épreuves, carte).
- **SC-004**: Un visiteur ne connaissant pas le mot de passe partagé n'obtient
  aucune donnée saisie par les déclarants sur les résultats en attente, dans
  100 % des tentatives d'accès direct à la page ou à ses données.
- **SC-005**: Un renommage d'épreuve ou une réattribution d'athlète qui
  produirait une collision ou un conflit est signalé au bénévole dans 100 %
  des cas, sans jamais aboutir à un doublon d'épreuve ou une participation
  incohérente en base.

## Assumptions

- Le mot de passe partagé est communiqué hors-bande (par un canal existant du
  club) aux 5-6 bénévoles ; sa distribution et son renouvellement ne sont pas
  du ressort de cette feature.
- La feature s'appuie sur `Participation.is_pending_validation` tel que produit
  par #270 (branche `20260814-130052-saisie-manuelle-resultats`, non fusionnée
  à ce jour) : aucun nouveau champ de validation n'est introduit ici.
- Les bénévoles opèrent depuis un navigateur standard (desktop ou mobile),
  sans exigence d'application dédiée.
- La réattribution ne porte que sur des athlètes déjà existants en base ; la
  création d'un athlète depuis cet écran n'est pas couverte (cf. Edge Cases).
- Le volume de résultats en attente à un instant donné reste de l'ordre de la
  dizaine à la centaine (saisie manuelle occasionnelle, pas un flux massif) —
  aucun chiffre n'étant donné par l'issue, cette hypothèse écarte le besoin
  d'une pagination sophistiquée dès cette spec ; à confirmer au plan si le
  volume réel diffère.
- Le mécanisme d'accès par mot de passe partagé est retenu tel qu'arbitré dans
  le fil de l'issue (cf. § Décisions actées), malgré la tension relevée dans
  le dernier commentaire du fil qui reste sans réponse écrite à ce jour.
- La session de bénévole ne porte pas d'expiration par délai d'inactivité :
  l'accès se referme à la fermeture du navigateur ou sur déconnexion
  explicite. Aucun des 8 commentaires de l'issue ne précise de durée ; ce
  comportement standard est retenu par défaut faute d'exigence contraire, à
  revoir au plan si un délai précis s'avère nécessaire.
