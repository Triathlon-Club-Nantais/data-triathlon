# Research: Code d'accès du site : affichage en clair, reword, validité 3 mois

Aucun `[NEEDS CLARIFICATION]` n'a subsisté dans `spec.md` : les décisions de
périmètre ont été tranchées par l'utilisateur avant la rédaction de la spec.
Ce document consigne les choix techniques restants, tous mineurs.

## Affichage en clair du champ de code d'accès

- **Decision**: passer `<Input type="password">` en `<Input type="text">` sur
  `frontend/components/site-access/SiteAccessGate.tsx`, de façon permanente
  (pas de bouton "afficher/masquer").
- **Rationale**: le code n'est pas un secret personnel à protéger visuellement
  contre un regard par-dessus l'épaule (c'est un code partagé, souvent recopié
  ou dicté) — l'attribut `type="password"` du navigateur n'apporte donc aucune
  garantie de sécurité ici, seulement une gêne de saisie.
- **Alternatives considered**: un bouton "afficher/masquer" (icône œil)
  aurait ajouté un état et une interaction pour un gain nul dans ce contexte
  — rejeté par le Principe VI (YAGNI) et par la demande explicite de
  l'utilisateur ("ne pas masquer... le texte doit être visible en clair").

## Reword "mot de passe" → "code d'accès"

- **Decision**: reformuler uniquement les textes visibles de
  `SiteAccessGate.tsx` (titre, libellé, texte d'aide, message d'erreur), sans
  toucher au champ JSON `password` de l'API ni aux identifiants techniques
  (`id="site-password"`, noms de variables/fonctions).
- **Rationale**: le champ API et les identifiants techniques sont invisibles
  à l'utilisateur (Principe I — English/technique) et le champ JSON fait
  partie du contrat `/api/v1` publié (Principe IV) — les renommer serait un
  changement de contrat hors périmètre de cette feature.
- **Alternatives considered**: étendre le reword à l'écran admin
  (`SiteAccessConfig.tsx`) — écarté, l'utilisateur a explicitement borné le
  périmètre à l'écran visiteur.

## Extension du TTL de session à 90 jours

- **Decision**: changer la valeur par défaut de
  `Settings.site_access_session_ttl_days` (`backend/app/core/config.py`) de
  `7` à `90`. Aucune variable d'environnement `SITE_ACCESS_SESSION_TTL_DAYS`
  n'est fixée explicitement en prod (`docs/ci-cd.md` : "défaut" dans les
  trois environnements) — changer le défaut suffit, sans configuration
  d'infrastructure à toucher.
- **Rationale**: même mécanique que les 7 jours actuels (expiration posée à
  la création de la session, pas de renouvellement glissant) — cohérent avec
  le patron déjà en place pour `AUTH_SESSION_TTL_DAYS`
  (`docs/superpowers/specs/2026-08-20-mot-de-passe-site-design.md`).
- **Alternatives considered**: un renouvellement glissant (l'expiration
  repousserait à chaque visite) — écarté, hors périmètre de la demande et
  changerait un comportement déjà spécifié ailleurs (design #509) sans
  nouvelle justification métier.
