---
theme: default
title: Résultats de compétition TCN
info: |
  Présentation globale du site data-triathlon (Triathlon Club Nord).
class: text-center
highlighter: shiki
lineNumbers: false
drawings:
  enabled: false
transition: slide-left
mdc: false
---

<img
  v-motion
  :initial="{ opacity: 0, scale: 0.8 }"
  :enter="{ opacity: 1, scale: 1, transition: { duration: 500 } }"
  src="/logo-tcn.png" class="mx-auto h-24 object-contain mb-8" />

<div
  v-motion
  :initial="{ opacity: 0, y: 30 }"
  :enter="{ opacity: 1, y: 0, transition: { duration: 500, delay: 150 } }"
>

# Résultats de compétition TCN

Centraliser, en un seul endroit, les résultats de tous les membres du club

</div>

<div
  v-motion
  :initial="{ opacity: 0 }"
  :enter="{ opacity: 1, transition: { duration: 500, delay: 400 } }"
  class="mt-10 text-sm opacity-60"
>
  Collez une URL de chronométrage, le reste suit tout seul
</div>

---
layout: two-cols
transition: fade
---

# Avant ce site

<v-clicks>

- Les résultats de chaque membre dorment sur des sites de chronométrage différents, un par organisateur d'épreuve
- Aucune vue d'ensemble du club sur une épreuve donnée
- Retrouver la performance d'un athlète demande de connaître le bon site, la bonne épreuve, la bonne page
- Rien n'est comparable ni agrégé

</v-clicks>

<div v-click class="mt-8 text-sm font-bold" style="color: var(--tcn-orange-deep)">
  Ce site remplace cette recherche manuelle par un import automatique
</div>

::right::

<div class="h-full flex flex-col items-center justify-center gap-3">
  <p class="text-xs uppercase tracking-wide opacity-50 mb-2">4 épreuves, 4 sites de chronométrage différents</p>
  <div v-motion :initial="{ opacity: 0, x: 40, rotate: -6 }" :enter="{ opacity: 1, x: 0, rotate: -6, transition: { duration: 400, delay: 200 } }" class="pill">chrono-site-1.fr</div>
  <div v-motion :initial="{ opacity: 0, x: 40, rotate: 4 }" :enter="{ opacity: 1, x: 0, rotate: 4, transition: { duration: 400, delay: 350 } }" class="pill">timing-organisateur.com</div>
  <div v-motion :initial="{ opacity: 0, x: 40, rotate: -3 }" :enter="{ opacity: 1, x: 0, rotate: -3, transition: { duration: 400, delay: 500 } }" class="pill">resultats-epreuve.net</div>
  <div v-motion :initial="{ opacity: 0, x: 40, rotate: 6 }" :enter="{ opacity: 1, x: 0, rotate: 6, transition: { duration: 400, delay: 650 } }" class="pill">chrono-autre-club.fr</div>
  <div v-motion :initial="{ opacity: 0 }" :enter="{ opacity: 1, transition: { duration: 400, delay: 900 } }" class="text-xs opacity-50 mt-4">un onglet par épreuve, aucun lien entre eux</div>
</div>

---
layout: center
---

# Le principe

<div class="flex items-center justify-center gap-6 text-2xl mt-10">
  <div v-motion :initial="{ opacity: 0, x: -40 }" :enter="{ opacity: 1, x: 0, transition: { duration: 400 } }" class="feature-card">URL de chronométrage</div>
  <div v-motion :initial="{ opacity: 0, scale: 0.5 }" :enter="{ opacity: 1, scale: 1, transition: { duration: 300, delay: 300 } }" class="text-5xl font-bold" style="color: var(--tcn-orange)">→</div>
  <div v-motion :initial="{ opacity: 0, x: -40 }" :enter="{ opacity: 1, x: 0, transition: { duration: 400, delay: 400 } }" class="feature-card">Récupération et stockage</div>
  <div v-motion :initial="{ opacity: 0, scale: 0.5 }" :enter="{ opacity: 1, scale: 1, transition: { duration: 300, delay: 700 } }" class="text-5xl font-bold" style="color: var(--tcn-orange)">→</div>
  <div v-motion :initial="{ opacity: 0, x: -40 }" :enter="{ opacity: 1, x: 0, transition: { duration: 400, delay: 800 } }" class="feature-card">Import de toute l'épreuve</div>
</div>

<div v-click class="mt-12 opacity-70">
  Une action manuelle (coller une URL), tout le reste est automatique
</div>

---

# Ajouter un résultat

<div class="flex items-center justify-center gap-6 mt-14 text-sm">
  <div v-motion :initial="{ opacity: 0, y: 25 }" :enter="{ opacity: 1, y: 0, transition: { duration: 400 } }" class="feature-card w-52 text-center">
    <div class="step-number">1</div>
    <p class="font-bold mt-2">Coller l'URL</p>
    <p class="opacity-70 text-xs mt-1">du résultat de l'athlète</p>
  </div>
  <div class="text-4xl font-bold" style="color: var(--tcn-orange)">→</div>
  <div v-motion :initial="{ opacity: 0, y: 25 }" :enter="{ opacity: 1, y: 0, transition: { duration: 400, delay: 250 } }" class="feature-card w-52 text-center">
    <div class="step-number">2</div>
    <p class="font-bold mt-2">Vérifier</p>
    <p class="opacity-70 text-xs mt-1">les données pré-remplies</p>
  </div>
  <div class="text-4xl font-bold" style="color: var(--tcn-orange)">→</div>
  <div v-motion :initial="{ opacity: 0, y: 25 }" :enter="{ opacity: 1, y: 0, transition: { duration: 400, delay: 500 } }" class="feature-card w-52 text-center">
    <div class="step-number">3</div>
    <p class="font-bold mt-2">Enregistrer</p>
    <p class="opacity-70 text-xs mt-1">et déclencher l'import</p>
  </div>
</div>

<div v-click class="mt-14 text-sm opacity-70">
  Aucune ressaisie manuelle des temps, du classement ou des catégories
</div>

---
layout: two-cols
---

# Import automatique de l'épreuve

<div v-motion :initial="{ opacity: 0, y: 30 }" :enter="{ opacity: 1, y: 0, transition: { duration: 500 } }" class="feature-card mt-8 mr-4">
  <p>Dès qu'un résultat est sauvegardé, tous les autres participants de la même épreuve sont importés en arrière-plan.</p>
</div>

::right::

<div class="h-full flex flex-col justify-center ml-4">
  <p class="text-sm mb-2 opacity-70">Import en cours…</p>
  <div class="progress-track">
    <div v-motion :initial="{ width: '2%' }" :enter="{ width: '76%', transition: { duration: 1400, delay: 300 } }" class="progress-fill"></div>
  </div>
  <p v-click class="text-xs opacity-60 mt-3">Une barre de progression suit l'avancement en direct, sans recharger la page</p>
</div>

---

# Tous les résultats

<div v-motion :initial="{ opacity: 0, y: 40 }" :enter="{ opacity: 1, y: 0, transition: { duration: 500 } }" class="feature-card mt-6">
  <p>Liste complète des épreuves importées.</p>
</div>

<div class="flex gap-3 justify-center mt-6">
  <span v-motion :initial="{ opacity: 0, y: 10 }" :enter="{ opacity: 1, y: 0, transition: { duration: 300, delay: 300 } }" class="pill">Nom</span>
  <span v-motion :initial="{ opacity: 0, y: 10 }" :enter="{ opacity: 1, y: 0, transition: { duration: 300, delay: 450 } }" class="pill">Type</span>
  <span v-motion :initial="{ opacity: 0, y: 10 }" :enter="{ opacity: 1, y: 0, transition: { duration: 300, delay: 600 } }" class="pill">Date</span>
</div>

<div v-click class="mt-6 text-sm opacity-70">
  Le point d'entrée pour retrouver n'importe quelle épreuve déjà importée sur le site
</div>

---
layout: two-cols
---

# Club TCN

<div v-motion :initial="{ opacity: 0, y: 30 }" :enter="{ opacity: 1, y: 0, transition: { duration: 500 } }" class="feature-card mt-8 mr-4">
  <p>Résultats et statistiques filtrés sur les membres du club.</p>
</div>

::right::

<div v-click class="h-full flex flex-col justify-center ml-4">
  <p class="text-lg font-bold" style="color: var(--tcn-orange-deep)">Co-membres automatiques</p>
  <p class="text-sm opacity-70 mt-2">Les co-membres présents sur une même épreuve apparaissent automatiquement, sans action supplémentaire.</p>
</div>

---

# Dashboard

<div class="grid grid-cols-3 gap-4 mt-10">
  <div v-motion :initial="{ opacity: 0, y: 30 }" :enter="{ opacity: 1, y: 0, transition: { duration: 400 } }" class="stat-tile">
    <span class="stat-number" style="font-size: 1.4rem">Club</span>
    <p class="text-sm mt-1">Chiffres clés filtrés sur le club</p>
  </div>
  <div v-motion :initial="{ opacity: 0, y: 30 }" :enter="{ opacity: 1, y: 0, transition: { duration: 400, delay: 180 } }" class="stat-tile">
    <span class="stat-number" style="font-size: 1.4rem">Disciplines</span>
    <p class="text-sm mt-1">Répartition triathlon, duathlon, aquathlon...</p>
  </div>
  <div v-motion :initial="{ opacity: 0, y: 30 }" :enter="{ opacity: 1, y: 0, transition: { duration: 400, delay: 360 } }" class="stat-tile">
    <span class="stat-number" style="font-size: 1.4rem">Temps réel</span>
    <p class="text-sm mt-1">Mis à jour à chaque import</p>
  </div>
</div>

---

# Recherche globale

<div v-motion :initial="{ opacity: 0, y: 20 }" :enter="{ opacity: 1, y: 0, transition: { duration: 400 } }" class="fake-search mt-14">
  <span class="opacity-50">Rechercher un athlète, une épreuve…</span>
</div>

<div v-click class="feature-card mt-8 max-w-lg mx-auto">
  <p>Barre de recherche accessible depuis le header, sur toutes les pages. Navigation instantanée vers le résultat recherché.</p>
</div>

---

# Bénévolat

<div v-motion :initial="{ opacity: 0, y: 40 }" :enter="{ opacity: 1, y: 0, transition: { duration: 500 } }" class="feature-card mt-6">
  <p>Déclarer une activité de bénévolat pour un athlète, instruite ensuite par un administrateur, qui compte pour son quota de saison.</p>
</div>

<div v-click v-motion :initial="{ opacity: 0, y: 40 }" :click-1="{ opacity: 1, y: 0, transition: { duration: 500 } }" class="feature-card mt-4">
  <p>Une file de vérification permet aux bénévoles du club de valider eux-mêmes des résultats en attente, sans passer par un administrateur pour chaque cas.</p>
</div>

---

# Une interface pour tout le monde

<div class="grid grid-cols-2 gap-6 mt-6">
  <div v-motion :initial="{ opacity: 0, y: 30 }" :enter="{ opacity: 1, y: 0, transition: { duration: 400 } }" class="feature-card">
    <p class="font-bold">Responsive</p>
    <p class="text-sm mt-2">Navigation mobile dédiée, formulaires adaptatifs</p>
  </div>
  <div v-motion :initial="{ opacity: 0, y: 30 }" :enter="{ opacity: 1, y: 0, transition: { duration: 400, delay: 200 } }" class="feature-card">
    <p class="font-bold">Accessible</p>
    <p class="text-sm mt-2">Lisible par tous, y compris au clavier</p>
  </div>
</div>

---
class: infographic-slide
---

# Contribuer au projet

<div class="grid grid-cols-2 gap-6 mt-10">
  <div v-motion :initial="{ opacity: 0, y: 30 }" :enter="{ opacity: 1, y: 0, transition: { duration: 400 } }" class="feature-card">
    <p class="font-bold">Open source sur GitHub</p>
    <p class="text-sm mt-2 opacity-80">Le code est public : signaler un bug, proposer une amélioration, ou contribuer directement.</p>
    <p class="text-xs mt-3" style="color: var(--tcn-orange-deep)">github.com/Triathlon-Club-Nantais/data-triathlon</p>
  </div>
  <div v-motion :initial="{ opacity: 0, y: 30 }" :enter="{ opacity: 1, y: 0, transition: { duration: 400, delay: 200 } }" class="feature-card">
    <p class="font-bold">Un bouton feedback dans l'appli</p>
    <p class="text-sm mt-2 opacity-80">Directement depuis le site, sans passer par GitHub : signaler un problème ou suggérer une idée en quelques clics.</p>
  </div>
</div>

---
layout: center
class: infographic-slide
---

<div class="flex flex-col items-center">
  <img
    v-motion
    :initial="{ opacity: 0, scale: 0.7 }"
    :enter="{ opacity: 1, scale: 1, transition: { duration: 600 } }"
    src="/logo-tcn.png" class="h-24 object-contain mb-8" style="filter: brightness(0) invert(1)" />

  <h1
    v-motion
    :initial="{ opacity: 0, y: 20 }"
    :enter="{ opacity: 1, y: 0, transition: { duration: 500, delay: 200 } }"
    class="text-5xl font-black mb-3" style="color: #ffffff"
  >Résultats de compétition TCN</h1>
  <p class="opacity-80 text-xl">Collez une URL, le club a ses résultats</p>

  <div v-motion :initial="{ opacity: 0 }" :enter="{ opacity: 1, transition: { duration: 400, delay: 500 } }" class="flex gap-3 mt-8">
    <span class="tri-dot" style="background: var(--tcn-ink)"></span>
    <span class="tri-dot" style="background: var(--tcn-orange-300)"></span>
    <span class="tri-dot" style="background: var(--tcn-orange)"></span>
  </div>

  <p v-motion :initial="{ opacity: 0, y: 10 }" :enter="{ opacity: 1, y: 0, transition: { duration: 400, delay: 700 } }" class="text-sm opacity-60 mt-8 max-w-md text-center">
    Bienvenue au club ! Voici l'outil qui centralise les résultats de tous les membres, pour ne plus jamais chercher une performance sur dix sites différents.
  </p>
</div>

---
layout: center
class: infographic-slide
---

<div class="flex flex-col items-center">
  <p v-motion :initial="{ opacity: 0 }" :enter="{ opacity: 1, transition: { duration: 400 } }" class="text-sm uppercase tracking-widest opacity-60 mb-10">Ce que permet le site</p>

  <div class="grid grid-cols-2 gap-x-16 gap-y-10 text-left max-w-3xl">
    <div v-motion :initial="{ opacity: 0, x: -20 }" :enter="{ opacity: 1, x: 0, transition: { duration: 400, delay: 200 } }" class="stat-block">
      <p class="stat-value text-xl">Import automatique</p>
      <p class="text-sm opacity-80">Toute l'épreuve importée dès qu'un résultat est ajouté</p>
    </div>
    <div v-motion :initial="{ opacity: 0, x: 20 }" :enter="{ opacity: 1, x: 0, transition: { duration: 400, delay: 300 } }" class="stat-block">
      <p class="stat-value text-xl">Club TCN</p>
      <p class="text-sm opacity-80">Statistiques et co-membres détectés automatiquement</p>
    </div>
    <div v-motion :initial="{ opacity: 0, x: -20 }" :enter="{ opacity: 1, x: 0, transition: { duration: 400, delay: 400 } }" class="stat-block">
      <p class="stat-value text-xl">Recherche globale</p>
      <p class="text-sm opacity-80">Un athlète ou une épreuve, retrouvés en un instant</p>
    </div>
    <div v-motion :initial="{ opacity: 0, x: 20 }" :enter="{ opacity: 1, x: 0, transition: { duration: 400, delay: 500 } }" class="stat-block">
      <p class="stat-value text-xl">Bénévolat</p>
      <p class="text-sm opacity-80">Déclaration et vérification intégrées au site</p>
    </div>
  </div>
</div>

---
layout: center
class: infographic-slide
---

<div class="flex flex-col items-center">
  <h1 v-motion :initial="{ opacity: 0, y: 20 }" :enter="{ opacity: 1, y: 0, transition: { duration: 400 } }" class="text-3xl font-black mb-10" style="color: #ffffff">Rejoindre et contribuer</h1>

  <div class="grid grid-cols-2 gap-x-12 gap-y-6 text-left max-w-3xl mb-10">
    <div v-motion :initial="{ opacity: 0, y: 20 }" :enter="{ opacity: 1, y: 0, transition: { duration: 400, delay: 200 } }">
      <p class="font-bold">Open source sur GitHub</p>
      <p class="text-sm opacity-80 mt-1">github.com/Triathlon-Club-Nantais/data-triathlon</p>
    </div>
    <div v-motion :initial="{ opacity: 0, y: 20 }" :enter="{ opacity: 1, y: 0, transition: { duration: 400, delay: 350 } }">
      <p class="font-bold">Un bug, une idée ?</p>
      <p class="text-sm opacity-80 mt-1">Le bouton feedback, directement dans l'appli</p>
    </div>
  </div>

  <div v-motion :initial="{ opacity: 0, y: 20 }" :enter="{ opacity: 1, y: 0, transition: { duration: 400, delay: 550 } }" class="access-panel">
    <img src="/qr-site.png" class="w-24 h-24 rounded" />
    <div class="text-left">
      <p class="font-bold">data.triathlon-club-nantais.com</p>
      <p class="text-sm opacity-80 mt-1">Code d'accès : <strong>HelloTCN2026</strong></p>
    </div>
  </div>

  <p v-motion :initial="{ opacity: 0 }" :enter="{ opacity: 1, transition: { duration: 400, delay: 750 } }" class="text-sm opacity-70 mt-8">
    Une question ? Thomas Jarrier (jarriert@gmail.com) · Mathieu Herrmann (mathieu.herrmann44@gmail.com)
  </p>
</div>
