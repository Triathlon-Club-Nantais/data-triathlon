# Feature Specification: Refonte du formulaire de saisie manuelle des résultats

**Feature Branch**: `20260814-130052-saisie-manuelle-resultats`

**Created**: 2026-08-14

**Status**: Draft

**Issue**: Closes #270

**Input**: User description: "Refonte du formulaire de saisie manuelle des résultats (issue #270) — champs obligatoires, retrait de genre/club/catégorie, taxonomie FFTri des épreuves, choix du format en deux temps, place générale, individuel/collectif, lien vers les résultats, encart temps adaptatif, contrôles bloquants à la soumission, et statut « en attente de validation »."

## Contexte

Le site importe automatiquement les résultats depuis 14 chronométreurs. Certaines
épreuves ne sont chronométrées par aucun d'eux, ou leurs résultats ne sont
jamais publiés en ligne : le formulaire de saisie manuelle est la seule voie
pour qu'un membre du club fasse figurer ce résultat sur sa fiche.

Le formulaire actuel a été conçu comme un miroir du modèle technique : il
demande à l'athlète des données qu'il ne connaît pas nécessairement (catégorie,
libellé exact du club tel que le chronométreur l'orthographie) et ne demande pas
celles qui font la valeur du résultat (place générale, épreuve en équipe, preuve
externe). Surtout, rien ne distingue ensuite un résultat déclaré par un membre
d'un résultat émis par un chronométreur : les deux entrent en base au même
niveau de confiance.

Cette spec couvre la **production** d'un résultat déclaré fiable et marqué comme
non encore vérifié. L'écran par lequel un bénévole le vérifie fait l'objet de
l'issue #271, traitée séparément.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Saisir un résultat sans se tromper (Priority: P1)

Un membre du club a terminé une épreuve qu'aucun chronométreur partenaire ne
publie. Il ouvre le formulaire de saisie, renseigne son identité, la date et le
nom de l'épreuve, et enregistre. S'il oublie une information indispensable, le
formulaire le lui dit champ par champ et refuse d'enregistrer tant que ce n'est
pas corrigé. On ne lui demande plus son genre, son club ni sa catégorie d'âge.

**Why this priority**: C'est le socle. Sans identité complète ni date, un
résultat ne peut être ni rattaché à un athlète, ni rapproché d'une épreuve
existante, ni vérifié par un bénévole — il produit une ligne orpheline que
quelqu'un devra nettoyer à la main. Livrée seule, cette histoire suffit déjà à
supprimer la principale cause de saisies inexploitables.

**Independent Test**: Ouvrir le formulaire, tenter d'enregistrer à vide, vérifier
qu'un message d'erreur apparaît sous chacun des quatre champs obligatoires et
que rien n'est enregistré ; puis les remplir et vérifier que l'enregistrement
aboutit et que les champs genre / club / catégorie ont disparu de l'écran.

**Acceptance Scenarios**:

1. **Given** le formulaire vide, **When** l'utilisateur clique sur « Enregistrer
   le résultat », **Then** un message d'erreur s'affiche sous le nom, le prénom,
   la date et le nom de l'épreuve, et aucun résultat n'est enregistré.
2. **Given** un formulaire où seul le prénom manque, **When** l'utilisateur
   soumet, **Then** le message ne porte que sur le prénom et l'enregistrement
   reste bloqué.
3. **Given** le formulaire affiché, **When** l'utilisateur le parcourt, **Then**
   aucun champ « Genre », « Club » ni « Catégorie » n'y figure.
4. **Given** les quatre champs obligatoires renseignés, **When** l'utilisateur
   soumet, **Then** le résultat est enregistré et l'utilisateur reçoit une
   confirmation.
5. **Given** le champ « Épreuve » du formulaire actuel, **When** l'écran est
   affiché, **Then** son libellé est « Nom de l'épreuve ».

---

### User Story 2 - Distinguer un résultat déclaré d'un résultat chronométré (Priority: P2)

Le résultat qu'un membre vient de saisir apparaît sur sa fiche athlète, mais
porte visiblement la mention qu'il est en attente de validation, et ne compte
encore dans aucune statistique, aucun podium ni aucun classement. Il reste dans
cet état tant qu'un bénévole ne l'a pas vérifié. Un visiteur qui consulte la
fiche comprend immédiatement que cette ligne est déclarative et non chronométrée.

**Why this priority**: C'est ce qui protège la crédibilité de l'ensemble des
données du site — sans cette distinction, une saisie erronée ou fantaisiste est
indiscernable d'un résultat officiel. C'est aussi la donnée que la file de
validation bénévole (#271) consommera : sans elle, cet écran n'a rien à lister.

**Independent Test**: Saisir un résultat au nom d'un athlète connu, ouvrir sa
fiche et vérifier que la ligne apparaît avec une mention « en attente de
validation » visuellement distincte des autres résultats ; puis vérifier que les
compteurs de la page club et les statistiques du tableau de bord n'ont pas bougé.

**Acceptance Scenarios**:

1. **Given** un résultat saisi manuellement, **When** il est enregistré, **Then**
   il porte l'état « en attente de validation ».
2. **Given** un résultat en attente de validation dont le nom correspond à un
   athlète connu, **When** on consulte la fiche de cet athlète, **Then** le
   résultat y figure avec une mention explicite de son état.
3. **Given** un résultat importé depuis un chronométreur, **When** il est
   enregistré, **Then** il ne porte aucune mention d'attente de validation.
4. **Given** un résultat en attente de validation, **When** aucun bénévole n'est
   intervenu, **Then** il conserve cet état indéfiniment (aucune validation
   automatique par ancienneté).
5. **Given** un résultat en attente de validation, **When** on consulte les
   statistiques du tableau de bord, les podiums et compteurs de la page club et
   le classement de l'épreuve concernée, **Then** ce résultat n'y figure ni n'y
   est compté.
6. **Given** un résultat passé à l'état validé, **When** on consulte ces mêmes
   écrans, **Then** il y est compté comme n'importe quel résultat importé.

---

### User Story 3 - Décrire précisément sa discipline (Priority: P3)

L'utilisateur choisit son épreuve parmi les disciplines de la fédération
française de triathlon. Pour un triathlon, un duathlon, un aquathlon ou un swim
bike, il précise ensuite le format (XS, S, M, L, XL, ou « Autre » avec une
précision obligatoire à la clé). Pour les autres disciplines, il indique
simplement la distance totale.

**Why this priority**: Un type d'épreuve juste conditionne le regroupement des
résultats, les statistiques par discipline et le rapprochement avec les épreuves
déjà en base. Trois disciplines demandées sont aujourd'hui absentes du
formulaire, ce qui force les membres concernés à ranger leur résultat sous une
étiquette fausse.

**Independent Test**: Ouvrir la liste des disciplines et vérifier que les huit
disciplines FFTri demandées y figurent ; sélectionner « Triathlon » et vérifier
l'apparition du choix de format ; sélectionner « Autre » et vérifier que le champ
de précision devient obligatoire ; sélectionner « Raid Multisport » et vérifier
qu'un champ de distance totale apparaît à la place du format.

**Acceptance Scenarios**:

1. **Given** le sélecteur de discipline, **When** il est déployé, **Then** il
   propose Triathlon, Duathlon, Swim & Run, Run & Bike, Raid Multisport, Cross
   Triathlon, Aquathlon et Swim Bike.
2. **Given** la discipline « Triathlon » sélectionnée, **When** l'écran se met à
   jour, **Then** un choix de format XS / S / M / L / XL / Autre apparaît.
3. **Given** le format « Autre » sélectionné, **When** l'utilisateur soumet sans
   remplir la précision, **Then** un message d'erreur bloque l'enregistrement.
4. **Given** la discipline « Raid Multisport » sélectionnée, **When** l'écran se
   met à jour, **Then** aucun choix de format n'apparaît et un champ de distance
   totale est proposé.
5. **Given** une discipline puis un format choisis, **When** le résultat est
   enregistré, **Then** il est rattaché à la même discipline que les résultats
   équivalents importés automatiquement.

---

### User Story 4 - Documenter et qualifier son résultat (Priority: P4)

L'utilisateur complète sa saisie : sa place générale, s'il a couru en individuel
ou en équipe (et dans ce cas le nom de l'équipe), s'il a terminé, abandonné ou
déclaré forfait, et un lien vers les résultats publiés qui permettra au bénévole
de vérifier. Les temps sont regroupés dans un encart à part, dont les champs
s'adaptent à la discipline choisie, et restent facultatifs.

**Why this priority**: Ces informations enrichissent le résultat et facilitent
la vérification, mais un résultat sans elles reste exploitable. Elles se posent
donc après le socle et l'état de validation.

**Independent Test**: Saisir un résultat en cochant « collectif », vérifier
l'apparition du champ « nom de l'équipe » et qu'il bloque la soumission s'il est
vide ; vérifier que l'encart des temps est visuellement séparé et qu'un
enregistrement aboutit avec tous ses champs de temps vides.

**Acceptance Scenarios**:

1. **Given** le formulaire, **When** il s'affiche, **Then** le choix
   individuel / collectif est proposé et positionné sur « individuel ».
2. **Given** « collectif » sélectionné, **When** l'écran se met à jour, **Then**
   un champ « nom de l'équipe » apparaît et devient obligatoire.
3. **Given** « collectif » puis à nouveau « individuel » sélectionné, **When**
   l'utilisateur soumet, **Then** le nom d'équipe éventuellement saisi n'est pas
   conservé et l'enregistrement aboutit.
4. **Given** un résultat enregistré avec un lien vers les résultats externes,
   **When** ce résultat est consulté, **Then** le lien est conservé et
   consultable.
5. **Given** un formulaire par ailleurs valide dont tous les champs de temps sont
   vides, **When** l'utilisateur soumet, **Then** l'enregistrement aboutit.
6. **Given** une discipline sans natation sélectionnée, **When** l'encart des
   temps s'affiche, **Then** il ne propose pas de temps de natation.
7. **Given** le formulaire, **When** il s'affiche, **Then** le statut sportif est
   proposé et positionné sur « terminée ».
8. **Given** le statut « abandon » sélectionné et aucun temps ni place générale
   renseignés, **When** l'utilisateur soumet, **Then** l'enregistrement aboutit.
9. **Given** un abandon déclaré puis validé par un bénévole, **When** on consulte
   le résultat, **Then** il est toujours un abandon.

---

### Edge Cases

- **Nom d'athlète non reconnu** : le résultat est saisi pour une personne dont
  aucun athlète existant ne porte l'identité. Le résultat est enregistré et reste
  en attente de validation ; c'est au bénévole de le rattacher (#271). Il
  n'apparaît sur aucune fiche athlète existante entre-temps.
- **Épreuve déjà en base** : le nom et la date saisis correspondent à une épreuve
  déjà importée depuis un chronométreur. Le résultat déclaré rejoint cette
  épreuve plutôt que d'en créer un doublon.
- **Doublon de la même personne** : un membre saisit deux fois le même résultat.
  Le second doit être détectable par le bénévole, pas silencieusement fusionné ni
  silencieusement rejeté.
- **Lien de résultats invalide** : l'utilisateur colle un texte qui n'est pas une
  adresse web exploitable. Le formulaire ne doit ni bloquer l'enregistrement sur
  ce seul motif, ni présenter ce texte comme un lien cliquable.
- **Changement de discipline après saisie des temps** : l'utilisateur remplit les
  temps d'un triathlon puis bascule sur « Course à pied ». Les temps devenus sans
  objet ne doivent pas être enregistrés silencieusement.
- **Format « Autre » avec une précision très longue** : la précision saisie ne
  doit pas casser l'affichage du libellé de discipline ailleurs sur le site.

## Requirements *(mandatory)*

### Functional Requirements

**Champs obligatoires et contrôles**

- **FR-001**: Le formulaire MUST rendre obligatoires le nom, le prénom, la date
  et le nom de l'épreuve.
- **FR-002**: Le champ « Épreuve » MUST être libellé « Nom de l'épreuve ».
- **FR-003**: Le formulaire MUST retirer de la saisie les champs genre, club et
  catégorie, sans que les données correspondantes cessent d'être renseignées par
  les imports automatiques.
- **FR-004**: À la soumission, le formulaire MUST vérifier tous les champs
  obligatoires, afficher un message d'erreur explicite au niveau de chaque champ
  fautif, et empêcher l'enregistrement tant qu'il subsiste une erreur.
- **FR-005**: Les messages d'erreur MUST être en français et désigner l'action à
  faire, pas la contrainte technique violée.

**Discipline et format**

- **FR-006**: Le sélecteur de discipline MUST proposer les huit disciplines
  fédérales citées par le porteur produit : Triathlon, Duathlon, Swim & Run,
  Run & Bike, Raid Multisport, Cross Triathlon, Aquathlon, Swim Bike.
- **FR-007**: Pour un triathlon, un duathlon, un aquathlon ou un swim bike, le
  formulaire MUST proposer un choix de format parmi XS, S, M, L, XL et « Autre ».
- **FR-008**: Le choix « Autre » MUST faire apparaître un champ de précision, et
  ce champ MUST être obligatoire dès lors que « Autre » est retenu.
- **FR-009**: Pour les disciplines sans format normalisé, le formulaire MUST
  proposer un champ de distance totale à la place du choix de format.
- **FR-010**: Un résultat saisi manuellement MUST être rattaché à la même
  discipline que les résultats équivalents importés automatiquement, afin que les
  regroupements et statistiques par discipline restent cohérents.

**Champs complémentaires**

- **FR-011**: Le formulaire MUST proposer un champ « place générale »,
  facultatif.
- **FR-012**: Le formulaire MUST proposer un choix obligatoire entre individuel
  et collectif, positionné par défaut sur individuel.
- **FR-013**: Le choix « collectif » MUST faire apparaître un champ « nom de
  l'équipe » obligatoire ; le choix « individuel » MUST le masquer et ne pas
  conserver sa valeur.
- **FR-014**: Le formulaire MUST proposer un champ permettant de saisir un lien
  vers les résultats publiés, facultatif, et ce lien MUST être conservé avec le
  résultat.
- **FR-015**: Les champs de temps MUST être regroupés dans un encart distinct du
  reste du formulaire, MUST s'adapter à la discipline choisie, et MUST rester
  tous facultatifs.

**État de validation**

- **FR-016**: Tout résultat créé par saisie manuelle MUST être marqué « en
  attente de validation » à l'enregistrement.
- **FR-017**: Un résultat issu d'un import automatique MUST NOT porter cet état.
- **FR-018**: Un résultat en attente de validation MUST rester dans cet état
  jusqu'à une action humaine explicite ; aucun mécanisme d'expiration ou de
  validation automatique n'est prévu.
- **FR-019**: Un résultat en attente de validation dont l'athlète est reconnu
  MUST apparaître sur la fiche de cet athlète, assorti d'une mention visuelle
  explicite de son état.
- **FR-020**: L'état « en attente de validation » MUST être exposé par l'API de
  lecture pour que la file de validation bénévole (#271) puisse s'y appuyer sans
  nouveau changement de contrat.
- **FR-021**: Un résultat en attente de validation MUST être exclu de **tous** les
  agrégats publics — statistiques du tableau de bord, podiums et compteurs de la
  page club, classements d'épreuve — jusqu'à sa validation. Sa seule surface
  d'affichage est la fiche de l'athlète concerné (FR-019).
- **FR-022**: Une fois validé, un résultat MUST entrer dans ces agrégats au même
  titre qu'un résultat importé, sans autre intervention.

**Statut sportif**

- **FR-023**: Le formulaire MUST permettre de déclarer une épreuve terminée, un
  abandon (DNF) ou un forfait (DNS), positionné par défaut sur « terminée ».
- **FR-024**: L'état « en attente de validation » MUST être porté indépendamment
  du statut sportif : un abandon déclaré reste un abandon une fois validé, et la
  validation ne doit jamais écraser le statut sportif saisi.
- **FR-025**: Un abandon ou un forfait déclaré MUST rester saisissable sans temps
  ni place générale.

### Key Entities

- **Résultat déclaré** : une performance saisie par un membre plutôt qu'importée.
  Porte l'identité de l'athlète, l'épreuve, la discipline et son format, la place
  générale, le caractère individuel ou collectif, le nom de l'équipe le cas
  échéant, les temps facultatifs, un lien de vérification, un statut sportif
  (terminée / abandon / forfait) et un état de validation.
- **Épreuve** : l'événement sportif auquel le résultat se rattache. Un résultat
  déclaré rejoint une épreuve existante lorsqu'elle correspond, et n'en crée une
  que sinon.
- **Athlète** : la personne créditée du résultat. Le rattachement se fait sur
  l'identité saisie ; son absence n'empêche pas l'enregistrement.
- **État de validation** : la qualification d'un résultat comme déclaratif non
  encore vérifié, ou vérifié. **Dimension distincte du statut sportif** : les
  deux se combinent librement (un abandon en attente de validation est un état
  légitime). Produit ici, consommé par #271.
- **Statut sportif** : terminée, abandon ou forfait. Existe déjà pour les
  résultats importés ; cette feature le rend saisissable à la main.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Un membre saisit un résultat complet en moins de 2 minutes, sans
  consulter d'aide extérieure.
- **SC-002**: 100 % des résultats saisis manuellement portent une identité
  complète (nom, prénom, date, nom d'épreuve) — soit zéro ligne inexploitable
  produite par le formulaire, contre ce que le formulaire actuel autorise.
- **SC-003**: Un visiteur distingue un résultat déclaré d'un résultat chronométré
  au premier coup d'œil sur une fiche athlète, sans survol ni clic.
- **SC-004**: Les huit disciplines fédérales demandées sont sélectionnables, et
  aucun membre n'a besoin de ranger son résultat sous une discipline approchante.
- **SC-005**: Aucune saisie manuelle ne devient visible comme résultat vérifié
  sans passage par une action humaine.
- **SC-006**: Aucune statistique, aucun podium et aucun classement publiés ne
  varient à la suite d'une saisie manuelle tant qu'elle n'est pas validée — zéro
  écart mesuré avant / après saisie sur ces écrans.
- **SC-007**: Un bénévole dispose, pour chaque résultat en attente, du lien de
  vérification quand le membre l'a fourni — mesuré sur la part des saisies qui en
  portent un.

## Assumptions

- **« Run & Bike » désigne la discipline déjà connue du site sous « Bike & Run »**
  — une seule et même discipline, pas deux entrées distinctes. **Confirmé par le
  porteur produit le 2026-08-14** : ce n'est plus une hypothèse, FR-006 ne se
  dédouble pas.
- **Trois disciplines sont réellement nouvelles** : Raid Multisport, Cross
  Triathlon et Swim Bike n'existent aujourd'hui sous aucune étiquette du site.
  Swim & Run correspond à la discipline déjà présente sous « SwimRun ».
- **Le format XL n'existe aujourd'hui que pour le triathlon** ; FR-007 l'ouvre
  aux quatre disciplines à format. L'aquathlon et le swim bike n'ont aujourd'hui
  aucun format déclinable, il faut les créer.
- **Le lien vers les résultats est une pièce justificative, pas une source de
  données** : il accompagne le résultat pour permettre sa vérification humaine et
  ne doit pas être traité comme une adresse à scraper, sous peine de faire entrer
  une épreuve déclarée dans le circuit de rafraîchissement automatique.
- **Aucune modification du contrôle d'accès** : qui a le droit de saisir un
  résultat manuel reste inchangé par cette feature.
- **La place générale reste facultative** : le porteur produit l'a listée parmi
  les ajouts sans la ranger parmi les champs obligatoires, contrairement aux
  quatre champs d'identité qu'il a explicitement nommés.
- **Les temps restent au format de saisie actuel** (HH:MM:SS), inchangé.
- **L'exclusion des agrégats est totale, pas graduée** (arbitrage du 2026-08-14,
  FR-021) : un résultat en attente ne compte nulle part, pas même dans un simple
  compteur de participations. La fiche athlète est sa seule surface d'affichage.
- **L'état de validation est une dimension à part entière** (arbitrage du
  2026-08-14, FR-024), et non une valeur supplémentaire du statut sportif : c'est
  ce qui permet de déclarer un abandon sans lui faire perdre cette qualité au
  moment de la validation.
- **L'action qui fait passer un résultat de « en attente » à « validé »
  appartient à #271.** Cette spec définit le comportement des deux états et la
  bascule de visibilité qui en découle, mais ne fournit pas le geste qui la
  déclenche. Vérifier FR-022 et le scénario 6 de la User Story 2 suppose donc de
  provoquer l'état validé par un autre moyen que l'interface bénévole.

## Hors périmètre

- **L'écran de validation par les bénévoles** — issue #271. Cette spec produit
  l'état « en attente de validation » et l'expose ; elle ne fournit ni la file de
  validation, ni l'édition du nom d'épreuve, ni la réattribution à un athlète,
  ni l'action de validation elle-même.
- **Le mécanisme d'accès des bénévoles** (page protégée par mot de passe, SSO
  Google) — arbitré sur #271, hors de cette feature.
- **La reprise des résultats manuels déjà en base** : les saisies antérieures ne
  sont pas rétroactivement marquées « en attente de validation ».
- **Les champs genre, club et catégorie** restent renseignés par les imports
  automatiques ; seule leur saisie manuelle disparaît.
