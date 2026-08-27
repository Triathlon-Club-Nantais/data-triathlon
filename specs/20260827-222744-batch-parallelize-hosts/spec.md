# Feature Specification: Parallélisation du batch d'import par hôte de chronométrage

**Feature Branch**: `20260827-222744-batch-parallelize-hosts`

**Created**: 2026-08-27

**Status**: Draft

**Input**: User description: "Issue #690 : paralléliser run_batch (backend/app/services/batch.py) par hôte de chronométrage. Constat mesuré sur le terrain : run_batch traite les épreuves strictement en séquence avec une pause de politesse fixe de 1s entre scrapes réels, quel que soit l'hôte. Sur des lots couvrant des dizaines de chronométreurs différents (145 épreuves → ~2h40, 483 épreuves → plus de 5h), cette sérialisation globale semble être le principal facteur de durée. Piste à concevoir : les épreuves d'un même hôte restent séquentielles (politesse), mais des hôtes différents peuvent scraper concurremment."

## Clarifications

### Session 2026-08-27

- Q: Quand une épreuve utilise l'un des chronométreurs qui publient sur
  plusieurs domaines distincts (Wiclax : `wiclax-results.com` /
  `chronosmetron.com` / `chronowest.fr` ; RaceResult : `raceresult.com` /
  `espace-competition.com` / `chronoconsult.fr`), le délai de politesse
  doit-il s'appliquer par domaine réseau exact, ou par chronométreur (tous ses
  domaines confondus) ? → A: Par chronométreur — tous les domaines qu'il
  publie forment un seul « hôte de chronométrage » au sens de cette
  spécification, sérialisé comme aujourd'hui, même si ses épreuves sont
  réparties sur plusieurs domaines réseau.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Réduire le temps mur d'un batch multi-hôtes (Priority: P1)

Un exploitant (ou le workflow planifié) déclenche un import de masse ou un
rescrape portant sur des dizaines d'épreuves réparties sur des dizaines de
chronométreurs différents. Il veut que le batch se termine en une fraction du
temps actuel, sans changer le volume de requêtes envoyées à chaque
chronométreur.

**Why this priority**: C'est le seul problème mesuré par l'issue — 145
épreuves en ~2h40, 483 épreuves en plus de 5h — et la seule raison d'ouvrir ce
chantier.

**Independent Test**: Lancer un batch sur un lot mêlant plusieurs dizaines
d'hôtes distincts et mesurer le temps mur ; il doit être significativement
inférieur à une exécution strictement séquentielle du même lot.

**Acceptance Scenarios**:

1. **Given** un lot de N épreuves réparties sur plusieurs hôtes distincts,
   **When** le batch s'exécute, **Then** des épreuves d'hôtes différents sont
   traitées en même temps et le temps mur total diminue par rapport à un
   traitement strictement séquentiel.
2. **Given** un lot ne portant que sur un seul hôte (ou moins d'hôtes que le
   plafond de concurrence), **When** le batch s'exécute, **Then** le temps mur
   total reste comparable à celui d'aujourd'hui — aucune régression faute
   d'opportunité de parallélisation.

---

### User Story 2 - Continuer à respecter la politesse envers chaque chronométreur (Priority: P1)

Le même exploitant ne veut pas que la parallélisation se traduise par des
requêtes plus fréquentes envers un chronométreur donné : le fournisseur tiers
ne doit voir aucun changement de rythme, seul le temps mur global change.

**Why this priority**: C'est la contrainte qui rend la parallélisation
acceptable — sans elle, l'issue proposerait de dégrader la relation avec les
chronométreurs pour gagner du temps, ce qui n'est pas le compromis recherché.

**Independent Test**: Sur un lot où plusieurs épreuves ciblent le même hôte,
vérifier qu'aucune paire de requêtes vers cet hôte ne part sans le délai de
politesse actuel entre elles, quel que soit ce qui se passe sur les autres
hôtes en parallèle.

**Acceptance Scenarios**:

1. **Given** un hôte portant plusieurs épreuves dans le lot, **When** le batch
   les traite, **Then** elles restent traitées en séquence pour cet hôte, avec
   le même délai de politesse qu'aujourd'hui entre deux d'entre elles.
2. **Given** plusieurs hôtes traités en parallèle, **When** l'un d'eux est
   plus lent que les autres, **Then** cela ne modifie pas le rythme de
   traitement des autres hôtes.

---

### User Story 3 - Garder un bilan et une supervision fiables malgré l'ordre non déterministe (Priority: P2)

Le même exploitant surveille la progression en direct (terminal ou logs CI) et
exploite le bilan final — y compris la sortie `--json` consommée par le
pipeline de rejeu des échecs (`rescrape-db --urls-from -`). Il veut que ce
bilan reste correct et exploitable même si les épreuves ne se terminent plus
dans l'ordre du lot d'entrée.

**Why this priority**: Le bilan et le pipeline de rejeu sont un contrat déjà
en place ; les casser en gagnant du temps mur remplacerait un problème par un
autre.

**Independent Test**: Comparer, sur un même lot, le bilan (compteurs, détail
des échecs, sources passives) d'une exécution parallélisée et d'une exécution
séquentielle : leur contenu doit être identique, à l'ordre près.

**Acceptance Scenarios**:

1. **Given** un batch parallélisé qui vient de se terminer, **When** on
   compare son bilan à celui d'une exécution séquentielle du même lot,
   **Then** les compteurs et le détail (échecs, sources passives,
   réconciliations) sont identiques.
2. **Given** un batch en cours d'exécution parallélisée, **When** l'exploitant
   observe la sortie de progression, **Then** il peut toujours distinguer quelles
   épreuves sont en cours et lesquelles sont terminées.
3. **Given** un Ctrl-C pendant un batch parallélisé, **When** le batch
   s'arrête, **Then** il émet un bilan partiel reflétant uniquement le travail
   déjà commité et sort avec le même code qu'aujourd'hui — sans perte ni
   incohérence, même si plusieurs hôtes étaient en cours de traitement au
   moment de l'interruption.

---

### Edge Cases

- Que se passe-t-il quand le nombre d'hôtes distincts dépasse le plafond de
  concurrence globale ? (Les hôtes excédentaires attendent qu'une place se
  libère, sans jamais dépasser le plafond.)
- Que se passe-t-il quand toutes les épreuves du lot ciblent le même hôte ?
  (Aucun gain de parallélisme n'est possible ni attendu ; le comportement doit
  rester celui d'aujourd'hui.)
- Que se passe-t-il quand une épreuve échoue pendant qu'un autre hôte est en
  cours de traitement ? (L'échec ne doit interrompre ni les autres épreuves du
  même hôte, ni celles des autres hôtes.)
- Que se passe-t-il sur un Ctrl-C alors que plusieurs hôtes traitent une
  épreuve en même temps ? (Le travail déjà commité par chaque hôte reste
  acquis ; le bilan partiel les reflète tous.)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Le système DOIT permettre à des épreuves d'hôtes de
  chronométrage différents d'être traitées en même temps au sein d'un même
  batch.
- **FR-002**: Le système DOIT continuer à traiter en séquence les épreuves
  d'un même hôte, en conservant entre elles le délai de politesse existant
  aujourd'hui — y compris quand ce chronométreur publie sur plusieurs domaines
  réseau distincts, tous regroupés sous ce même hôte.
- **FR-003**: Le système DOIT plafonner le nombre d'hôtes traités
  simultanément, pour ne pas saturer la machine qui exécute le batch.
- **FR-004**: Le bilan final d'un batch (compteurs d'épreuves et de
  participants, détail des échecs, des sources passives et des
  réconciliations) DOIT être équivalent — à l'ordre de présentation près — à
  celui d'une exécution strictement séquentielle du même lot d'épreuves.
- **FR-005**: La sortie machine-lisible (`--json`) DOIT conserver son schéma
  actuel, indépendamment de l'ordre, désormais non déterministe, dans lequel
  les hôtes terminent leur traitement.
- **FR-006**: L'exploitant DOIT continuer à disposer d'une progression en
  temps réel pendant l'exécution, lui permettant de distinguer les épreuves en
  cours des épreuves terminées.
- **FR-007**: Une interruption (Ctrl-C) DOIT continuer à produire un bilan
  partiel fidèle au travail déjà commité, puis à sortir avec le même code
  qu'aujourd'hui — y compris quand plusieurs hôtes sont en cours de traitement
  au moment de l'interruption.
- **FR-008**: Un batch qui n'offre pas d'opportunité de parallélisation (un
  seul hôte, ou moins d'hôtes que le plafond de concurrence) DOIT s'exécuter
  sans régression de temps mur par rapport à aujourd'hui.
- **FR-009**: Une épreuve en échec DOIT continuer à ne jamais interrompre le
  traitement des autres épreuves, que ce soit sur le même hôte ou sur un autre
  hôte en cours de traitement.
- **FR-010**: La parallélisation DOIT bénéficier à toute commande qui
  s'appuie sur la boucle de batch commune, sans dupliquer la règle de
  politesse par hôte à chaque appelant.

### Key Entities

- **Épreuve à traiter** : une URL à scraper et son libellé d'affichage ;
  rattachée à un hôte de chronométrage par son URL.
- **Hôte de chronométrage** : le chronométreur (fournisseur tiers) qui publie
  une ou plusieurs épreuves du lot — tous les domaines réseau qu'il publie
  comptent comme un seul hôte ; unité à l'intérieur de laquelle le traitement
  reste séquentiel.
- **Bilan de batch** : l'agrégat final (compteurs, listes d'échecs, de sources
  passives, de réconciliations) qui doit rester stable en contenu quel que
  soit l'ordre de traitement retenu.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Sur un lot de plusieurs dizaines d'hôtes distincts comparable au
  cas mesuré sur le terrain, le temps mur total du batch diminue d'au moins
  50 % par rapport à une exécution strictement séquentielle du même lot.
- **SC-002**: Sur un lot qui ne porte que sur un seul hôte, le temps mur total
  du batch ne se dégrade pas par rapport à l'exécution actuelle.
- **SC-003**: Sur 100 % des exécutions comparées, le bilan d'un batch
  parallélisé (compteurs, échecs, sources passives, réconciliations) contient
  exactement les mêmes éléments qu'une exécution séquentielle du même lot.
- **SC-004**: Sur 100 % des exécutions interrompues par Ctrl-C, le batch
  parallélisé émet un bilan partiel fidèle au travail déjà commité et sort
  avec le même code qu'aujourd'hui.
- **SC-005**: Sur 100 % des exécutions, aucun chronométreur — tous domaines
  confondus — ne reçoit jamais deux requêtes de scraping en même temps.

## Assumptions

- Le degré de concurrence globale (combien d'hôtes au maximum en parallèle)
  est un point de conception à trancher au moment du plan, pas de cette
  spécification ; il doit rester ajustable sans changer le comportement
  observable décrit ici.
- Le format externe de `--json` (les champs qu'il expose) ne change pas ;
  seul l'ordre interne de traitement des hôtes devient non déterministe.
- Aucun consommateur actuel ne dépend de l'ordre des listes du bilan
  (`failures`, `passive_sources`, `reassignments`) : le pipeline de rejeu des
  échecs n'en extrait que les URLs, sans égard à leur position.
- Une progression entrelacée entre plusieurs hôtes (au lieu d'un flux
  stationnaire par épreuve) est un compromis acceptable en échange d'un temps
  mur réduit.
- Les deux commandes qui s'appuient aujourd'hui sur la boucle de batch commune
  (import de masse et rescrape) bénéficient de la même parallélisation, sans
  logique dupliquée entre elles.
