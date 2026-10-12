# Sondage lenteur de la fiche épreuve (#1302)

Mesuré le 12/10/2026 dans Chrome (onglet au premier plan, session avec code
d'accès), sur la preview puis sur la production. API appelée depuis la page,
par le proxy `/api` de Next.

## Constat de départ

Le 10/10, sur la preview, `/courses/460` (Swimrun Court Duo, 177 résultats) est
resté plus de 15 s sur son squelette, et une capture d'écran a échoué après 30 s.

## Preview, à chaud : rien de lent

| Mesure | 20 lignes | 177 lignes (`page_size=all`) |
| --- | --- | --- |
| Premier octet (squelette en streaming) | 25 ms | 26 à 38 ms |
| Fin du flux HTML (données serveur reçues) | 946 ms | 906 ms à 2,5 s |
| HTML décodé | 160 ko | 742 ko |
| LCP (le `h1`) | 1,7 s | 2,6 s |
| Nœuds DOM | 892 | 4 348 |
| Longues tâches | aucune | aucune |

- API, 3 essais chacune : `GET /courses/460` 154 à 234 ms (20 lignes) et
  ~295 ms (177 lignes, 148 ko) ; `summary` 110 à 132 ms ; `sources` 78 à 118 ms.
- Rendu client des 177 lignes, mesuré sur une navigation interne avec un
  observer posé avant (`longtask` et `long-animation-frame` vérifiés sur une
  tâche témoin de 150 ms) : lignes visibles en 783 ms, dont 665 ms de charge RSC
  (12 ko compressés), **aucune longue tâche**.
- Aucun préchargement au défilement : les liens de ligne portent
  `prefetch={false}`.

## Ce qui n'a pas pu être reproduit : le froid

La preview est maintenue chaude par le keep-warm et suspendue par le coucher
horaire (#1319) : elle passe de « suspendue » (503 immédiat) à « chaude », sans
état de mise en veille Render mesurable. Au réveil du 12/10, le backend a
répondu 503, puis une requête est restée sans réponse avant le premier 200.

## Piège de mesure relevé

Un onglet Chrome **masqué** (`visibilityState: hidden`, fenêtre réduite ou
derrière une autre) ne peint pas : aucun `first-paint`, aucun LCP, et une
capture d'écran peut échouer. C'est cohérent avec la capture en échec du 10/10,
prise par un agent dont l'onglet n'était pas au premier plan. Toute mesure de
rendu commence donc par vérifier `document.visibilityState`.

## Cause nommée

Pas de lenteur du rendu ni de l'API à chaud sur 177 lignes. Le symptôme du 10/10
s'explique par un backend pas encore servi (réveil après suspension), combiné à
une mesure dans un onglet masqué.

La lenteur réelle de la fiche épreuve est ailleurs, et se mesure en production
sur une grosse épreuve en « Tout » : `/courses/955?page_size=all` (3 003
résultats) produit 16,9 Mo de HTML, un flux complet en 10,5 s et un LCP à
11,3 s. Le correctif est suivi par **#1355** ; le temps API (4 s) dépend de la
table `participations` gonflée, suivie par **#1352**.
