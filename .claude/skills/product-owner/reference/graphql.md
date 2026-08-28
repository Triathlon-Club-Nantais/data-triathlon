# Mécaniques GitHub GraphQL/CLI pour `/product-owner`

`gh` v2.45 (version installée sur les postes de dev) n'expose pas la
relation *sub-issue* ni l'ajout d'options à un champ de projet existant en
commande dédiée — ce fichier documente les appels `gh api graphql`
nécessaires. Confirmé le 28/08/2026 par introspection du schéma
(`gh api graphql -f query='{ __type(name: "...") { ... } }'`).

## IDs du projet « Data TCN »

| Élément | ID |
| --- | --- |
| Projet (owner `Triathlon-Club-Nantais`, #1) | `PVT_kwDOEaPNkc4Bdwm2` |
| Champ `Status` | `PVTSSF_lADOEaPNkc4Bdwm2zhYP1fg` |
| Champ `Priority` | `PVTSSF_lADOEaPNkc4Bdwm2zhYP1qQ` |

Si un appel échoue avec « field not found », ré-résoudre avec :
```bash
gh project field-list 1 --owner Triathlon-Club-Nantais
```

## Node ID d'une issue

Les mutations GraphQL utilisent l'ID de nœud (`node_id`), pas le numéro :
```bash
gh api repos/Triathlon-Club-Nantais/data-triathlon/issues/<numéro> -q .node_id
```

## Lier une sous-issue à une epic

```bash
gh api graphql -f query='
mutation($issueId: ID!, $subIssueId: ID!) {
  addSubIssue(input: { issueId: $issueId, subIssueId: $subIssueId }) {
    issue { number }
  }
}' -f issueId="<node_id de l'epic>" -f subIssueId="<node_id de la sous-issue>"
```

## Priority est un Issue Field partagé, pas un champ de projet

`Priority` (id projet `PVTSSF_lADOEaPNkc4Bdwm2zhYP1qQ`) a `isIssueField:
true` — c'est le miroir d'un `IssueFieldSingleSelect` au niveau de
l'organisation (id `IFSS_kgDOApchLg`), avec déjà 4 options configurées :

| Valeur | id d'option |
| --- | --- |
| Urgent | `IFSSO_kgDOBIiAkQ` |
| High | `IFSSO_kgDOBIiAkg` |
| Medium | `IFSSO_kgDOBIiAkw` |
| Low | `IFSSO_kgDOBIiAlA` |

Confirmé le 28/08/2026 par introspection :
```bash
gh api graphql -f query='
{
  node(id: "PVTSSF_lADOEaPNkc4Bdwm2zhYP1qQ") {
    ... on ProjectV2SingleSelectField {
      isIssueField
      issueField { ... on IssueFieldSingleSelect { id options { id name } } }
    }
  }
}'
```

`updateProjectV2Field` échoue sur ce champ (« Only custom fields can be
updated. Fields derived from issues or pull requests must be updated
through their respective APIs. ») — **ne pas tenter de le recréer ou de le
renommer**, ces options existent déjà et sont potentiellement partagées
avec d'autres repos/projets de l'organisation ; les modifier aurait un
effet de bord hors du seul board « Data TCN ».

## Poser Status sur un item du board

Il faut d'abord l'ID d'*item* de projet (pas le node_id de l'issue) :
```bash
gh project item-list 1 --owner Triathlon-Club-Nantais --limit 500 --format json \
  -q '.items[] | select(.content.number == <numéro>) | .id'
```
`--limit` par défaut est 30 et tronque silencieusement (aucune erreur) —
le board compte plusieurs centaines d'items, toujours le préciser.

Puis (Status est un champ de projet normal, `isIssueField: false`), une
seule valeur de champ par appel (limite de `gh project item-edit`) :
```bash
gh project item-edit \
  --project-id "PVT_kwDOEaPNkc4Bdwm2" \
  --id "<item id>" \
  --field-id "PVTSSF_lADOEaPNkc4Bdwm2zhYP1fg" \
  --single-select-option-id "<option id de Status>"
```

## Poser Priority sur une issue

Priority ne se pose **pas** via `gh project item-edit` — côté projet, ses
options sont vides (seul le champ organisation en a). Il faut la mutation
`updateIssueFieldValue`, sur le node_id de l'**issue** (pas de l'item de
projet), avec l'id d'option de la table ci-dessus :
```bash
gh api graphql -f query='
mutation($issueId: ID!, $fieldId: ID!, $optionId: ID!) {
  updateIssueFieldValue(input: {
    issueId: $issueId
    issueField: { fieldId: $fieldId, singleSelectOptionId: $optionId }
  }) {
    clientMutationId
  }
}' -f issueId="<node_id de l'issue>" -f fieldId="IFSS_kgDOApchLg" -f optionId="<id de l'option>"
```

## Échec partiel

`gh project item-edit`/`gh api graphql` renvoient un code de sortie non nul
et un message d'erreur JSON en cas d'échec — capturer stdout/stderr, ne pas
masquer l'erreur, et lister explicitement à l'utilisateur les paires
(item, champ) qui n'ont pas pu être appliquées, sans retenter
automatiquement.
