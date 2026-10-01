# Quickstart: Textes légaux du site

## Tests

```bash
cd frontend
npm test -- components/legal app/routes-garde-site.test.ts app/page-titles.test.tsx components/layout/VersionFooter.test.tsx
npm run lint && npm run build
```

## Vérification manuelle

1. `uv run python scripts/dev_server.py` (dans `backend/`), puis `npm run dev`.
2. Navigation privée, aucun cookie : ouvrir `/acces`. Le pied de page montre
   les trois liens ; chacun ouvre sa page sans demander le code.
3. Sur `/confidentialite` : la date de mise à jour est en tête ; le sommaire
   mène aux rubriques ; l'adresse `president@triathlon-club-nantais.com` et le
   lien vers la CNIL sont cliquables.
4. Largeur 320 px : les trois liens restent visibles, sans défilement
   horizontal.
5. Après saisie du code, une page d'épreuve et `/admin` portent le même pied
   de page.
