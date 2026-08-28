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

## Configurer le champ Priority (à faire une seule fois — voir Task 4)

```bash
gh api graphql -f query='
mutation($fieldId: ID!) {
  updateProjectV2Field(input: {
    fieldId: $fieldId
    singleSelectOptions: [
      { name: "🔴 Urgent", color: RED, description: "" }
      { name: "🟠 High", color: ORANGE, description: "" }
      { name: "🟡 Medium", color: YELLOW, description: "" }
      { name: "🟢 Low", color: GREEN, description: "" }
    ]
  }) {
    projectV2Field { ... on ProjectV2SingleSelectField { id options { id name } } }
  }
}' -f fieldId="PVTSSF_lADOEaPNkc4Bdwm2zhYP1qQ"
```

Récupérer les `option.id` retournés — nécessaires pour poser une valeur sur
un item (étape suivante).

## Poser Status/Priority sur un item du board

Il faut d'abord l'ID d'*item* de projet (pas le node_id de l'issue) :
```bash
gh project item-list 1 --owner Triathlon-Club-Nantais --format json \
  -q '.items[] | select(.content.number == <numéro>) | .id'
```

Puis, une seule valeur de champ par appel (limite de `gh project item-edit`) :
```bash
gh project item-edit \
  --project-id "PVT_kwDOEaPNkc4Bdwm2" \
  --id "<item id>" \
  --field-id "PVTSSF_lADOEaPNkc4Bdwm2zhYP1qQ" \
  --single-select-option-id "<option id>"
```

## Échec partiel

`gh project item-edit`/`gh api graphql` renvoient un code de sortie non nul
et un message d'erreur JSON en cas d'échec — capturer stdout/stderr, ne pas
masquer l'erreur, et lister explicitement à l'utilisateur les paires
(item, champ) qui n'ont pas pu être appliquées, sans retenter
automatiquement.
