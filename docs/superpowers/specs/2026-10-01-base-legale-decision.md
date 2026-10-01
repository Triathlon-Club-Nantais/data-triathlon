# Décision : base légale du traitement des données de résultats (RGPD)

**Date** : 2026-10-01
**Issue** : #332 (epic #313)
**Objet** : arrêter la base légale du traitement des résultats nominatifs, ce
qu'elle implique pour les données déjà en base, la position sur le scraping
fournisseur par fournisseur, et le recours à un conseil extérieur.
**Statut** : décision. Les textes publics (#333) et le droit d'opposition (#334)
s'y réfèrent au lieu de la rejouer. Les faits mesurés ci-dessous priment : une
divergence avec le code se tranche en re-mesurant.

> **Ce document est publié** (`docs/` alimente GitHub Pages). Il ne cite aucun
> secret.

## Ce qui est traité, mesuré le 2026-10-01

| Qui | Données | Où |
| --- | --- | --- |
| Tout participant d'une épreuve importée | nom, prénom, sexe, club déclaré, catégorie d'âge, dossard, temps, splits, classements, statut (finisher, abandon…), nom d'équipe de relais, ligne brute publiée par la source | `models/athlete.py`, `models/participation.py` |
| Idem, fermé derrière `athletes:read` | date de naissance | `core/permissions.py` |
| Auteur d'une saisie manuelle | les champs du résultat déclaré et un lien de preuve | `schemas/participation.py` |
| Utilisateur connecté (back-office) | e-mail et nom affiché lus chez GitHub, identifiant GitHub, sessions (empreinte du jeton, expiration), journal de ses actions d'administration | `models/user.py`, `identity.py`, `user_session.py`, `admin_action_log.py` |
| Auteur d'un signalement (#267) | titre, texte libre, page, navigateur, **adresse IP** (limitation de débit, jamais renvoyée par l'API) | `models/user_feedback.py` |
| Jeunes de l'école de triathlon | identité, date de naissance, contact d'urgence, notes, présence aux séances, fermé derrière `jeunes:read` | `models/personal_profile.py` |
| Tout visiteur | mesure d'audience PostHog (région UE), en production : pages vues, interactions (autocapture), erreurs ; pour un utilisateur connecté, `identify()` transmet e-mail, nom affiché et rôles (`frontend/app/providers.tsx`) | `frontend/instrumentation-client.ts`, `backend/app/core/analytics.py` |

Provenance des résultats : 14 chronométreurs (`backend/app/scrapers/AGENTS.md`),
atteints par le lien d'une épreuve collé par un membre ou par un fichier de
liens importé par un administrateur (`admin_batches`, `sheet_source` : le
fichier ne porte que des liens, jamais de résultats), et la saisie manuelle,
ouverte sans compte et masquée de tout agrégat tant qu'un bénévole ne l'a pas
validée. La saisie manuelle ne passe pas par le filtre des jeunes (#881).

Trois garde-fous déjà en place pèsent dans la balance :

- **Accès fermé** : tout le site public et toute l'API sont derrière le code
  d'accès partagé du club (#509, `api/v1/router.py`). Les résultats ne sont pas
  publiés sur Internet, ils sont consultés par les adhérents.
- **Non-indexation** : le front renvoie `X-Robots-Tag: noindex, nofollow` sur
  toutes ses routes (#860). Le constat DP-1 de l'audit OWASP (API servant des
  noms sans session) est caduc depuis #509.
- **Mineurs** : les épreuves et catégories jusqu'à Minime inclus ne sont pas
  importées (#881, `core/youth.py`).

## Décision : intérêt légitime (article 6.1.f du RGPD)

**Responsable de traitement** : l'association Triathlon Club Nantais.

**Intérêt poursuivi** : permettre aux adhérents de suivre leurs résultats et
ceux du club, de se situer dans le classement complet de chaque épreuve (#272),
et d'animer la vie associative (saisons, bénévolat). Le classement complet est
nécessaire à ce dernier point : sans les autres participants, la position d'un
adhérent n'a pas de sens.

**Mise en balance** :

- les données sont peu intrusives (aucune donnée sensible au sens de
  l'article 9) et ont déjà été rendues publiques par le chronométreur, à des
  fins identiques (faire connaître le classement) ;
- la réutilisation reste interne au club : accès par code, non-indexation,
  aucun usage commercial, aucune cession ;
- les mineurs de moins de 15 ans environ sont exclus ;
- la CNIL admet la publication de résultats sportifs sous réserve d'information
  des personnes et d'un droit d'opposition effectif
  ([FAQ sport amateur](https://www.cnil.fr/fr/sport-amateur-hors-contrat/questions-reponses)).

**Leviers écartés** :

- *Anonymisation* et *ciblage des seuls adhérents* : ils retirent le classement
  nominatif des pages d'épreuve et la comparaison au classement (#272), c'est-à-dire
  le cœur du produit, pour un gain de protection faible au regard d'un accès
  déjà fermé.
- *Consentement* : il est impossible à recueillir auprès de non-adhérents
  qu'on ne connaît que par une ligne de classement.
- *Partenariat* : solution durable, hors de portée à court terme sur 14
  fournisseurs. Il reste la voie pour les trois sources dont le `robots.txt`
  ferme les routes utilisées (voir plus bas).

**Ce que ce choix coûte au produit**, et qui devient obligatoire :

1. **Informer** (articles 13 et 14) : une politique de confidentialité publique,
   lisible **sans** le code d'accès, puisque les non-adhérents ne l'ont pas
   (#333). La CNIL a sanctionné la Fédération Française d'Athlétisme en 2014
   (délibération n°2014-293) pour n'avoir pas informé les non-licenciés :
   l'argument de « l'effort disproportionné » n'a pas été retenu.
2. **Rendre l'opposition effective** (article 21) : un point de contact relevé
   (`president@triathlon-club-nantais.com`, le représentant légal), et un retrait réel des résultats d'une personne qui s'y oppose (#334). Le
   retrait est la règle ; un refus doit être motivé au cas par cas.
3. **Fixer et tenir des durées de conservation** (ci-dessous).

Le traitement des données des **utilisateurs du back-office** repose sur le même
intérêt légitime (administrer le service et en tracer les actions). Celui des
**jeunes de l'école de triathlon** relève de l'adhésion au club (exécution du
contrat d'adhésion, article 6.1.b) et des obligations de sécurité de
l'encadrement.

## Données déjà en base

Conservées telles quelles : aucune anonymisation rétroactive. Elles ont été
collectées dans les mêmes conditions que celles qui suivront, et la politique
publiée vaut information pour elles aussi. Les oppositions reçues s'y
appliquent dès #334.

## Durées de conservation

| Données | Durée | État |
| --- | --- | --- |
| Résultats et athlètes | tant que le service existe (archive sportive du club), sauf opposition | tenu de fait |
| Signalements, dont l'adresse IP | 12 mois après leur dépôt | **purge à implémenter** |
| Journal des actions d'administration | 12 mois | **purge à implémenter** |
| Compte du back-office | tant que l'adresse figure sur la liste d'autorisation | suppression de compte à implémenter |
| Session de connexion | 7 jours | tenu (`auth_session_ttl_days`) |
| Cookie du code d'accès | 90 jours | tenu (`site_access_session_ttl_days`) |
| Profils jeunes | durée de l'adhésion, plus une saison | **purge à implémenter** |

Les purges marquées « à implémenter » font l'objet de #1158. La
politique annonce ces durées : tant qu'une purge n'est pas livrée, la durée
annoncée n'est pas tenue, ce qui doit rester un état transitoire court.

## Scraping, fournisseur par fournisseur

Ce que fait l'outil : sur l'URL d'une épreuve collée par un membre, il lit une
fois le classement de cette épreuve, puis le relit par batch tant que l'épreuve
est récente. Ce n'est pas un parcours systématique des sites. La source de
chaque résultat est conservée et affichée.

`robots.txt` relevé le 2026-10-01 sur les hôtes appelés par
`backend/app/scrapers/` :

| Fournisseur | Hôte appelé | `robots.txt` sur les routes utilisées |
| --- | --- | --- |
| Klikego | `www.klikego.com` | `/resultats/…` autorisé |
| Breizh Chrono | `resultats.breizhchrono.com` | `/resultats-courses/…` autorisé |
| TimePulse | `www.timepulse.fr` | autorisé (seul `/ajax/` fermé) |
| Sportinnovation | `sportinnovation.fr` | autorisé (`/api/` fermé, non utilisé) |
| ProLiveSport | `api.prolivesport.fr` | **`Disallow: /`** |
| Chronoplace | `www.chronoplace.fr` | autorisé |
| Wiclax / G-Live | `*.wiclax-results.com`, `www.chronowest.fr` | pas de `robots.txt` / tout autorisé |
| RaceResult | `my.raceresult.com` | **`Disallow: /*/*/list`**, la route `/{id}/results/list` est visée |
| T2Area (FFTRI) | `fftri.t2area.com` | autorisé (`/api/` fermé, non utilisé) |
| Competitor (Ironman) | `api.competitor.com`, `labs-v2.competitor.com` | pas de `robots.txt` |
| ok-time | `classement.ok-time.fr` | pas de `robots.txt` |
| runnerbreizh | `www.runnerbreizh.fr` | tout autorisé |
| Sporthive (MYLAPS) | `eventresults-api.speedhive.com` | **`Disallow: /`** |
| chronoweb | `chronoweb.com` | tout autorisé, `Crawl-delay: 3600` |

**Position** :

- `robots.txt` (RFC 9309) vise les robots d'exploration ; il n'a pas de force
  juridique propre, mais il exprime la volonté de l'éditeur et pèse dans
  l'appréciation d'une extraction. Les **trois** sources qui ferment
  explicitement les routes utilisées (ProLiveSport, RaceResult, Sporthive) sont
  maintenues en connaissance de cause, avec une demande d'autorisation à leur
  adresser ; un refus explicite d'un éditeur entraîne le retrait du
  fournisseur.
- chronoweb : une requête par épreuve, sans parcours, reste compatible avec
  l'esprit d'un délai d'exploration.
- **Droit du producteur de base de données** (article L341-1 du code de la
  propriété intellectuelle) : l'extraction du classement complet d'une épreuve
  peut constituer l'extraction d'une partie substantielle. Le risque est
  atténué (usage non commercial, interne, source citée, une épreuve à la fois),
  pas supprimé. C'est le levier *partenariat* qui le lève.
- Les CGU des fournisseurs n'ont pas été relues une à une : aucun n'a fait
  savoir au club une opposition. La relecture accompagne la demande
  d'autorisation aux trois sources ci-dessus.

## Conseil extérieur

**Sollicité, sans bloquer la publication.** La base légale et l'information des
personnes suivent la doctrine publiée de la CNIL et ne justifient pas
d'attendre un avis pour publier la politique : ne rien publier est la situation
la moins conforme. En revanche, le droit du producteur de base de données et la
réutilisation de résultats d'épreuves fédérales ne sont pas couverts par cette
doctrine : la question est posée au référent de la Fédération Française de
Triathlon (ou de la ligue Pays de la Loire), qui encadre les épreuves dont
proviennent la plupart des résultats.

## Hors de cette décision, signalé

- **Téléphone de l'éditeur** : la LCEN (article 6) l'exige d'un éditeur
  personne morale. Le site du club n'en publie aucun ; les mentions légales
  donnent ceux des trois hébergeurs, relevés sur leurs pages officielles.
  **Manquement accepté** (2026-10-01) : le club publie son adresse postale et
  une adresse électronique relevée, pas de numéro.

- **Mesure d'audience PostHog**, tranchée dans #1159 : les deux voies à la
  fois. Par défaut, mesure **sans cookie** (`cookieless_mode: "on_reject"`,
  opt-out par défaut, ni autocapture ni `identify()`), exemptée de
  consentement. Un bandeau propose la mesure détaillée (cookies, autocapture,
  `identify()`), refus et accord au même niveau, choix gardé six mois et
  modifiable depuis la politique de confidentialité. Les événements serveur
  du back-office restent rattachés à l'identifiant du compte, sans traceur
  dans le navigateur, sur la base de l'intérêt légitime à administrer le site.
  Retirer son accord arrête la mesure détaillée sans effacer ce qui a été
  transmis : le profil PostHog d'un utilisateur se supprime sur demande
  d'effacement, à la main depuis PostHog.
