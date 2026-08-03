# Charges utiles GitHub — fixtures du socle d'authentification (#114)

Quatre charges utiles couvrant les quatre formes que le fournisseur GitHub doit
savoir lire. Aucune n'est appelée sur le réseau : elles alimentent un
`httpx.MockTransport` (Principe III).

| Fichier | Route d'origine | Ce qu'il éprouve |
| --- | --- | --- |
| `github_access_token.json` | `POST https://github.com/login/oauth/access_token` | Échange du code. |
| `github_user_avec_email.json` | `GET https://api.github.com/user` | Chemin nominal : le profil publie une adresse, et `/user/emails` est appelé **quand même** — c'est lui qui porte `verified` (FR-005). L'adresse du profil n'est qu'un dernier repli. |
| `github_user_sans_email.json` | `GET https://api.github.com/user` | `email: null` — c'est le cas majoritaire, GitHub masquant l'adresse par défaut. Déclenche le repli. |
| `github_user_emails.json` | `GET https://api.github.com/user/emails` | Le repli. Porte une adresse **non vérifiée** et une adresse `noreply`, pour que la sélection ne puisse pas se réduire à « la première ». |

**Provenance** : reconstituées d'après le schéma publié par l'API GitHub (champs,
types et valeurs `null` compris), et non capturées sur un compte réel — créer une
application OAuth et donner un consentement demande un humain, ce que
`quickstart.md` prend en charge. Les champs que le scraper ne lit pas (`blog`,
`followers`, …) sont conservés : une fixture réduite à ce qu'on lit ne prouve
pas qu'on sait ignorer le reste.

**Une valeur s'écarte volontairement du format réel** : `access_token` ne porte
pas le préfixe `gho_` des jetons GitHub. Le dépôt a déjà payé une fois le prix
d'une fixture ressemblant à un secret — une clé Google dans un HTML chronoweb,
signalée par le *secret scanning* et triée à la main. Aucun test ne lit cette
valeur (le fournisseur la confie à Authlib, qui la repose en en-tête), donc la
ressemblance ne prouve rien et ne coûte que du bruit. Même convention que
`test_provider_errors.py`, qui répond `"access_token": "x"`.

Le champ qui décide est `verified`, jamais `primary` seul : une adresse primaire
non vérifiée ne certifie rien (FR-005).
