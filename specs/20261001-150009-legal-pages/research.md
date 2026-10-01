# Research: Textes légaux du site

## R1. Où ranger les pages pour qu'elles échappent au code d'accès

- **Decision**: trois dossiers à la racine d'`app/`, frères de `acces/`.
- **Rationale**: la garde vit dans `app/(public_restricted)/layout.tsx` et ne
  s'applique qu'à ce groupe ; `frontend/proxy.ts` ne filtre pas sur le code
  d'accès. `routes-garde-site.test.ts` verrouille déjà ce placement pour
  `acces`, `login`, `benevoles`, `admin`.
- **Alternatives considered**: un groupe `app/(legal)/` (une indirection de
  plus sans bénéfice pour trois pages).

## R2. Format du contenu

- **Decision**: un module TSX par texte, exportant un `LegalDocument`
  (titre, date, rubriques dont le contenu est du JSX).
- **Rationale**: aucune bibliothèque markdown dans `frontend/package.json` ;
  le précédent `/guide` porte son contenu en données TypeScript typées ; le JSX
  rend nativement liens `mailto:`, listes et tableaux (cookies).
- **Alternatives considered**: markdown + `react-markdown` (dépendance
  nouvelle) ; données purement textuelles comme le guide (ne porte ni lien ni
  tableau).

## R3. Pied de page

- **Decision**: un composant `LegalLinks` rendu dans le `<footer>` de
  `VersionFooter`, au-dessus de la version.
- **Rationale**: `VersionFooter` est le seul pied de page, rendu par le layout
  racine sur toutes les routes, y compris `/acces`. Liens `next/link`,
  couleur `--tcn-orange-deep` pour tenir 4,5:1 (même arbitrage que
  `GuideSommaire`), regroupés dans un `<nav aria-label="Informations légales">`.
- **Alternatives considered**: un second `<footer>` dans le layout (deux
  landmarks `contentinfo`, ambigus pour un lecteur d'écran).

## R4. Faits à publier, mesurés

Source : décision #332 et l'inventaire du code du 2026-10-01.

| Rôle | Société | Adresse | Localisation des données |
| --- | --- | --- | --- |
| Front | Vercel Inc. | 440 N Barranca Ave #4133, Covina, CA 91723, États-Unis | fonctions serveur sans région configurée (défaut Vercel : États-Unis) |
| API | Render Services, Inc. | 525 Brannan Street, Suite 300, San Francisco, CA 94107, États-Unis | Francfort (`render.yaml`) |
| Base de production | Microsoft Ireland Operations Ltd (Azure) | One Microsoft Place, South County Business Park, Leopardstown, Dublin 18, Irlande | France Central |
| Base de préproduction | Supabase Inc. | 970 Toa Payoh North #07-04, Singapour 318992 | non documentée |
| Connexion (SSO) et traitements planifiés | GitHub, Inc. | 88 Colin P. Kelly Jr. Street, San Francisco, CA 94107, États-Unis | États-Unis |
| Mesure d'audience | PostHog Inc. | 2261 Market Street #4008, San Francisco, CA 94114, États-Unis | Union européenne (instance UE) |

Transferts hors UE (Vercel, GitHub, Render pour la société mère) : encadrés par
le cadre de protection des données UE‑États‑Unis ou par des clauses
contractuelles types, selon le prestataire. Point non vérifié prestataire par
prestataire : la politique le formule sans affirmer une certification
particulière.

CNIL : 3 place de Fontenoy, TSA 80715, 75334 Paris Cedex 07 ;
plainte en ligne sur `https://www.cnil.fr/fr/plaintes`.

Cookies et stockage (inventaire du code) : `tcn_session` (7 jours),
`tcn_auth_state` (10 minutes), `tcn_logged_in` (7 jours), `tcn_site_session`
(90 jours), `tcn_benevole_session` (session du navigateur), `tcn-nav-expanded`
(1 an), `localStorage` `tcn-athlete`, `sessionStorage` `tcn_retour_connexion`,
traceurs PostHog en production.
