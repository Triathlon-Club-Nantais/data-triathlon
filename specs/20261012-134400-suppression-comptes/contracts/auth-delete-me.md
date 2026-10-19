# Contrat : `DELETE /api/v1/auth/me`

Supprime le compte de la session courante (US1). Aucun corps de requête.

| Cas | Statut | Corps | Cookies |
|---|---|---|---|
| Session valide, suppression faite | 204 | vide | session, `tcn_logged_in` et cookie bénévoles effacés (mêmes attributs que la pose) |
| Anonyme, jeton invalide ou compte désactivé | 401 | `{"detail": ...}` | inchangés |
| Compte cité par une donnée à référence obligatoire | 409 | `{"detail": "Votre compte est encore cité par des actions du club et ne peut pas être supprimé ici. Contactez le club pour le faire supprimer."}` | inchangés |
| Dernier administrateur | 409 | `{"detail": "Cette opération laisserait l'installation sans aucun administrateur."}` | inchangés |
| Écriture same-site ou cross-site | 403 | (`core/origin_guard`) | inchangés |

En-têtes : `Cache-Control: no-store`, `Vary: Cookie` sur toutes les réponses du préfixe.

Effets : voir `data-model.md` § Suppression d'un compte. Une ligne `account.delete` au journal, `payload = {"origin": "request", "entra_oids": [...]}`.
