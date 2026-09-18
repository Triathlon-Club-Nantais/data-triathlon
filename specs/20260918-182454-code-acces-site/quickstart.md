# Quickstart : valider la feature "code d'accès du site"

## Prérequis

- Backend et frontend démarrés en dev (`docs/dev-multi-worktree.md` : ports
  publiés automatiquement par worktree).
- Un code d'accès de site déjà configuré en base de dev (seed par défaut de
  `scripts/reset_db.py`, ou généré via `/admin/acces`).

## Scénario 1 — affichage en clair (US1, FR-001)

1. Ouvrir `/acces` dans le navigateur.
2. Saisir des caractères dans le champ de code d'accès.
3. **Attendu** : chaque caractère reste visible en clair pendant la saisie
   (pas de points noirs).

## Scénario 2 — vocabulaire "code d'accès" (US3, FR-002, FR-004)

1. Sur `/acces`, lire le titre, le libellé du champ et le texte d'aide.
2. Saisir un code incorrect et lire le message d'erreur.
3. **Attendu** : aucun de ces textes n'emploie "mot de passe".
4. Ouvrir `/admin/acces` (en étant authentifié admin).
5. **Attendu** : cet écran continue d'employer "mot de passe" (hors
   périmètre, non régressé).

## Scénario 3 — session valable 90 jours (US2, FR-003)

1. Valider le code d'accès sur `/acces`.
2. Inspecter le cookie de session posé par le navigateur
   (`tcn_site_session`) : sa date d'expiration (`Max-Age`/`Expires`) doit
   correspondre à 90 jours après la validation, pas 7.
3. **Attendu** : `max_age` du cookie = `90 * 24 * 60 * 60` secondes
   (vérifiable aussi par `uv run pytest backend/tests/test_auth/test_site_access_gate.py -m "not integration"`).

## Vérification automatisée

```bash
# Backend
uv run pytest -m "not integration"   # depuis backend/

# Frontend
npm test                              # depuis frontend/
```

Les deux suites doivent être vertes, avec les assertions de
`SiteAccessGate.test.tsx` et `test_site_access_gate.py` mises à jour pour
refléter le nouveau vocabulaire et le nouveau TTL (cf. `tasks.md`).
