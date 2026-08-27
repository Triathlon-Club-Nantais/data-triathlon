# Contrat CLI : parallélisation du batch par chronométreur

Interface exposée par `import-sheet` et `rescrape-db` (`backend/app/cli/`).
Tout ce qui n'est pas listé comme « nouveau » reste **strictement inchangé** —
c'est le contrat du Principe IV de la constitution.

## Nouvelle option

```text
--max-concurrent-hosts INTEGER   Plafond de chronométreurs traités en même
                                  temps (défaut : 4).
```

- Présente sur les deux commandes qui appellent `run_batch` (`import-sheet`,
  `rescrape-db`), même nom, même sémantique, même défaut sur les deux.
- Une valeur `1` revient au comportement strictement séquentiel d'aujourd'hui
  (utile pour un diagnostic, ou pour un environnement où même le degré de
  concurrence par défaut serait indésirable).
- Erreur d'usage (code **2**, comme les autres options invalides de la CLI) si
  la valeur n'est pas un entier strictement positif.
- N'affecte jamais le nombre de requêtes envoyées à un chronométreur donné —
  seul le nombre de chronométreurs traités en même temps varie.

## Inchangé (rappel du contrat existant, `backend/app/cli/AGENTS.md`)

- **stdout** : uniquement le rapport texte, ou uniquement la ligne `--json`
  avec `--json` — jamais les deux mélangés.
- **stderr** : progression (Rich en TTY, lignes simples sinon) et logs.
- **Codes de sortie** : `0` succès (y compris partiel ou « rien à faire »),
  `1` échec total (`errors >= épreuves > 0`), `2` erreur d'usage, `130`
  Ctrl-C — toujours précédé de l'émission du bilan (même partiel).
- **Schéma `--json`** : mêmes clés qu'aujourd'hui (`CHAMPS_COMMUNS` de
  `app/services/batch.py`) — `imported`, `updated`, `skipped`, `errors`,
  `processed`, `interrupted`, `failures`, `passive_sources`, plus les champs
  propres à chaque commande. Le **contenu** de `failures`/`passive_sources`
  reste équivalent à une exécution séquentielle ; seul leur **ordre** peut
  différer d'un run à l'autre (non déterministe dès qu'il y a plus d'un
  chronométreur dans le lot).
- **Progression affichée** : toujours au moins une ligne/mise à jour par
  épreuve démarrée et par épreuve terminée — désormais annotée du
  chronométreur concerné, pour rester lisible quand plusieurs épreuves sont en
  cours en même temps.
