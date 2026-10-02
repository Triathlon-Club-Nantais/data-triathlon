# Data Model: Textes légaux du site

Aucune donnée persistée. Un seul type de contenu, en mémoire.

## LegalDocument

| Champ | Type | Règle |
| --- | --- | --- |
| `title` | string | titre affiché et titre de document (onglet) |
| `description` | string | chapeau de la page |
| `updatedAt` | string ISO `YYYY-MM-DD` | affiché « Dernière mise à jour : 1 octobre 2026 » ; modifié dans le même commit que le texte |
| `sections` | `LegalSection[]` | au moins une ; sommaire affiché au-delà de 4 |

## LegalSection

| Champ | Type | Règle |
| --- | --- | --- |
| `id` | string | slug d'ancre, unique dans le document |
| `title` | string | titre de rubrique (`h2`) |
| `content` | ReactNode | paragraphes, listes, tableaux, liens |

## LegalRoute

Source unique des trois liens : `{ href, label }` pour `/mentions-legales`
(« Mentions légales »), `/confidentialite` (« Confidentialité »), `/cgu`
(« Conditions d'utilisation »).
