# Contract: `DELETE /api/v1/admin/volunteer-actions/{action_id}`

Additif au routeur existant `app/api/v1/admin_volunteer_actions.py` — ne
modifie aucune route en place (Principe IV).

## Requête

- **Méthode** : `DELETE`
- **Chemin** : `/api/v1/admin/volunteer-actions/{action_id}`
- **Garde** : `require_permission(P.ATHLETES_VOLUNTEER_VALIDATE)` — même
  pouvoir que `accept`/`reject`/la liste des validées.
- **Corps** : aucun.

## Réponses

| Statut | Cas | Corps |
|---|---|---|
| `204 No Content` | Déclaration supprimée, quel que soit son statut de départ (`en_attente`/`validee`/`refusee`) | vide |
| `404 Not Found` | `action_id` inexistant ou déjà supprimé | `{"detail": "Déclaration introuvable."}` |
| `401 Unauthorized` | Pas de session | — (comportement générique `require_permission`) |
| `403 Forbidden` | Session sans `athletes:volunteer_validate` | — (comportement générique `require_permission`, aucun détail du pouvoir manquant dans le corps) |

## Effets de bord

- Retire définitivement la ligne `volunteer_actions` (pas de soft-delete).
- Écrit une ligne `AdminActionLog` (`action="athlete.volunteer_action.
  delete"`, `entity_type="athlete"`, `entity_id=<athlete_id de la
  déclaration>`, `payload` portant `season`/`action_id`/`status` d'origine).
- Si la déclaration était `validee` : le quota de saison de l'athlète
  (`GET /admin/athletes/{id}/season-quota`) reflète son retrait au prochain
  appel — aucun cache serveur à invalider, `exists_for_athlete_season` relit
  la table à chaque appel.

## Client front (`lib/api/client.ts`)

```text
deleteVolunteerAction: (id: number) =>
  request<void>(`/admin/volunteer-actions/${id}`, { method: "DELETE" }),
```

Consommé par deux mutations distinctes (`lib/queries/admin.ts`), une par
écran d'exposition — cf. research.md D6 pour leurs invalidations respectives.
