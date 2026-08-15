# Quickstart : vérifier le résultat

Aucun serveur à lancer — feature documentaire. Vérification par lecture et
mesure.

```bash
# 1. Taille des deux fichiers allégés (cible : ≥ 40 % de réduction)
wc -l backend/app/api/AGENTS.md backend/app/services/auth/AGENTS.md

# 2. Les nouveaux fichiers de référence existent et sont non vides
wc -l docs/api/courses-sources-fusion.md docs/api/admin-donnees.md \
      docs/api/feedback-stats.md docs/auth/liste-autorisation.md \
      docs/auth/groupes.md

# 3. Aucune information perdue : chaque section déplacée reste retrouvable
#    (renvoi explicite depuis le fichier d'origine)
grep -n "docs/api/\|docs/auth/" backend/app/api/AGENTS.md backend/app/services/auth/AGENTS.md

# 4. Les 3 conventions apparaissent dans AGENTS.md racine
grep -n "assign\|Principe I\|commentaire" AGENTS.md

# 5. Lint prose : pas de outil automatisé — relecture manuelle suffit
#    (pas de code exécutable, donc pas de pytest/ruff à lancer pour cette
#    partie ; ruff/pytest restent lancés en fin de branche par hygiène)
```

Résultat attendu : les deux fichiers `AGENTS.md` de dossier repassent sous
~300 lignes chacun, les 5 nouveaux fichiers `docs/` portent l'intégralité du
contenu déplacé, et `AGENTS.md` racine gagne moins de 15 lignes nettes.
