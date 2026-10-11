# Implementation Plan: Comptes membres, socle

**Branch**: `epic/1312-member-accounts` (sous-branches `feat/1334-member-email-list`, `feat/1322-open-sign-in`, `feat/1323-entra-external-id`, empilées dans cet ordre) | **Date**: 2026-10-11 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/20261011-155714-comptes-membres-socle/spec.md`. Le sondage `docs/superpowers/specs/2026-10-11-comptes-membres-sondage.md` prime.

## Summary

Trois livraisons, une PR chacune vers la branche d'epic :

1. **#1334** : table `member_emails` (adresse normalisée, saison, origine), import CSV/XLSX de l'export AssoConnect calqué sur `club_members_service.import_file`, écran `/admin/adresses-adherents`, commande `import-member-emails`, purge dans `purge-retention`, pouvoir `member_emails:manage`, avenant RGPD.
2. **#1322** : `provisioning.resolve_user` ne consulte plus `allowed_emails` pour refuser ; un statut adhérent dérivé (`membership.is_member(db, user, today)`) dispense de la garde `require_site_access` ; `/auth/me` expose `is_member` ; le retour de parcours renvoie un non-administrateur vers `/` ; `serverFetch` relaie aussi le cookie de session SSO.
3. **#1323** : fournisseur `entra` dans `services/auth/idp/` (Authlib `OAuth2Client` + PKCE + nonce, validation de l'`id_token` par joserfc contre le JWKS de la découverte, e-mail accepté si `xms_edov` vrai) ; infrastructure dans `infra/entra-external-id/` : Bicep pour le tenant, script Graph idempotent pour l'application, Google et le parcours d'inscription.

## Technical Context

**Language/Version**: Python 3.13 (backend), TypeScript / Next.js 16 (frontend), Bicep + bash/az CLI (infra)

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, Alembic, Authlib 1.8 (`OAuth2Client`, `authlib.oidc.core.CodeIDToken`), joserfc 1.7 (JWT, `KeySet`), Typer ; aucune dépendance nouvelle

**Storage**: PostgreSQL (prod), SQLite (dev/tests) ; une table nouvelle `member_emails`, une migration Alembic

**Testing**: pytest sans réseau (`httpx.MockTransport` pour Entra, clé RSA générée par joserfc dans les tests), vitest côté frontend

**Target Platform**: Render (backend), Vercel (frontend), Azure (tenant Entra External ID lié à « Abonnement TCN »)

**Project Type**: application web (backend + frontend) et infrastructure as code

**Performance Goals**: le statut adhérent ajoute au plus une requête indexée par requête protégée d'un visiteur connecté sans cookie de site ; découverte OIDC et JWKS mis en cache en mémoire (1 h), rafraîchis une fois sur `kid` inconnu

**Constraints**: budget zéro (pas de Front Door, pas de SMS, pas de client credentials) ; aucune sortie HTTP hors `core.http.guarded_transport()` ; routes `def` (limiteur AnyIO à 40) ; pas d'appariement de comptes par adresse

**Scale/Scope**: ~300 adresses d'adhérents par saison, ~1 000 comptes au plus

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principe | Statut | Justification (si ⚠️ ou N/A) |
|---|----------|--------|-------------------------------|
| I | Langue métier français / technique English | ✅ | Identifiants anglais (`member_emails`, `is_member`, `EntraIdentityProvider`), messages `DomainError` et UI en français, tests en anglais pour les nouveaux fichiers. |
| II | Architecture en couches (api → services → repositories → DB) | ✅ | `member_email_repository` seul à requêter ; `membership` et `member_emails_service` côté services ; la garde de `deps.py` appelle le service. |
| III | TDD sans réseau (non-négociable) | ✅ | Chaque tâche de code a sa tâche de test écrite avant ; Entra testé contre `MockTransport` et jetons signés localement ; le test réel sur tenant est une procédure d'exploitation (FR-021), hors suite. |
| IV | Contrats API et CLI stables | ✅ | Ajouts seulement : routes `/admin/member-emails*`, champ `is_member` sur `/auth/me`, commande `import-member-emails`, méthode `entra` dans `/auth/methods`. Le changement de comportement (connexion hors liste acceptée sans droit) est l'objet même de #1322 et ne modifie aucun schéma. |
| V | Neutralité par défaut des paramètres transverses | N/A | Aucun paramètre transverse (`scope`, `federal_only`) touché. |
| VI | Simplicité / YAGNI | ✅ | Statut adhérent dérivé à la volée (pas de colonne, pas de cache) ; une seule table ; pas d'extension Entra ; pas de Terraform (état distant à héberger). |

Re-check post-design : inchangé.

## Project Structure

### Documentation (this feature)

```text
specs/20261011-155714-comptes-membres-socle/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── admin-member-emails.md
│   ├── auth.md
│   └── cli-import-member-emails.md
└── tasks.md
```

### Source Code (repository root)

```text
backend/
├── alembic/versions/<rev>_member_emails.py            # #1334
├── app/
│   ├── models/member_email.py                          # #1334
│   ├── repositories/member_email_repository.py         # #1334
│   ├── services/member_emails_service.py               # #1334 import/ajout/retrait
│   ├── services/membership.py                          # #1322 is_member, adresse retenue
│   ├── services/retention_service.py                   # #1334 purge
│   ├── services/auth/provisioning.py                   # #1322
│   ├── services/auth/idp/entra.py                      # #1323
│   ├── services/auth/idp/registry.py                   # #1323
│   ├── core/permissions.py                             # #1334 member_emails:manage
│   ├── core/config.py                                  # #1323 AUTH_ENTRA_*
│   ├── api/deps.py                                     # #1322 dispense de la garde site
│   ├── api/v1/admin_member_emails.py                   # #1334
│   ├── api/v1/auth.py                                  # #1322 redirection, is_member
│   ├── schemas/member_email.py, schemas/auth.py
│   └── cli/commands/import_member_emails.py, cli/reports.py, cli/__init__.py
└── tests/ (test_services, test_api, test_cli, test_auth, test_core_http.py)

frontend/
├── app/admin/adresses-adherents/{layout,page}.tsx       # #1334
├── components/admin/MemberEmailsPanel.tsx               # #1334
├── components/layout/nav.config.ts                      # #1334
├── components/site-access/SiteAccessGate.tsx            # #1322 lien de connexion, message non-adhérent
├── components/legal/content/confidentialite.tsx         # #1334, #1323
├── lib/api/server.ts                                    # #1322 relais du cookie de session
├── lib/{api/client.ts,queries/admin.ts,queries/keys.ts,types.ts,constants.ts}
└── app/login/page.tsx                                   # #1323 libellé du bouton (rendu générique déjà en place)

infra/entra-external-id/                                 # #1323
├── AGENTS.md, CLAUDE.md
├── main.bicep, main.bicepparam
└── configure-tenant.sh

docs/
├── superpowers/specs/2026-10-01-base-legale-decision.md # avenant #1334
├── auth/membres.md                                      # nouveau : liste d'adhérents et statut adhérent
├── infra-azure.md, ci-cd.md
└── backend/README.md (table AUTH_*)
```

**Structure Decision**: application web existante ; nouvelle racine `infra/entra-external-id/` à côté de `infra/azure-functions/`, avec son couple `AGENTS.md`/`CLAUDE.md`.

## Livraison

| Ordre | Sous-issue | Branche | Cible | Dépend de |
|---|---|---|---|---|
| 1 | #1334 | `feat/1334-member-email-list` | `epic/1312-member-accounts` | rien |
| 2 | #1322 | `feat/1322-open-sign-in` | `feat/1334-member-email-list` puis rebase sur l'epic | `member_email_repository` |
| 3 | #1323 | `feat/1323-entra-external-id` | `feat/1322-open-sign-in` puis rebase sur l'epic | règles d'ouverture de #1322 |

Chaque PR de sous-issue porte `Refs #1312` et `Refs #<sous-issue>` (`docs/gestion-de-projet.md` ; un `Closes` ne se déclenche qu'au merge sur la branche par défaut). La PR parapluie `epic/1312-member-accounts` → `main` porte `Closes #1312`, `Closes #1334`, `Closes #1322`, `Closes #1323`.

## Complexity Tracking

Aucune violation.
