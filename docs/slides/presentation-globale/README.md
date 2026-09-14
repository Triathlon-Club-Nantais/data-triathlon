# Présentation globale (Slidev)

Deck présentant le site data-triathlon dans son ensemble : le principe (coller
une URL, import automatique), les fonctionnalités, puis trois slides
infographie très synthétiques en clôture.

Ces trois dernières slides servent aussi de livrable autonome pour la journée
des nouveaux membres (couverture, fonctionnalités, contribution + accès au
site) : exportées en PNG, elles sont prévues pour être intégrées telles
quelles dans un autre deck (voir `export/nouveaux-*.png`).

## Lancer le deck

Depuis `docs/slides/` :

```bash
npm install
npm run dev
```

Ouvre le deck sur `http://localhost:3030`, avec rechargement à chaud.

## Exporter en PDF (deck complet)

```bash
npx slidev export presentation-globale/slides.md --output presentation-globale/dist/presentation-globale.pdf
```

## Ré-exporter les slides pour la journée des nouveaux

Après toute modification des trois dernières slides de `slides.md` :

```bash
npm run export:journee-nouveaux
```

Régénère `export/nouveaux-1-couverture.png`, `export/nouveaux-2-fonctionnalites.png`
et `export/nouveaux-3-contribution-acces.png`. Si le nombre de slides du deck
change, mettre à jour les numéros de page dans le script
`export:journee-nouveaux` de `package.json` (ils pointent sur les trois
dernières slides).
