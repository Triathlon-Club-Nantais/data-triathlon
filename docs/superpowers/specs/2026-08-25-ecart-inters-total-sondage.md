# Sondage — l'écart entre le temps total et la somme des inters (`RES-10`, lot #486)

**Date** : 2026-08-25 · **Lot** : #486 · **Entrée** : `RES-10` du § 6 de
`2026-08-20-ui-ux-challenge-audit.md` · **Base sondée** : `backend/triathlon.db`
(dev), 72 épreuves, 11 629 participations, 10 873 athlètes.

Ce document est un **sondage** : il consigne ce qui a été mesuré sur le terrain, et il
**prime** sur le design, la spec et le plan du lot. Toute divergence se tranche en
re-sondant, pas en arbitrant sur pièces.

## Ce qui était proposé

L'audit propose, pour `RES-10` :

> Ajouter une garde d'affichage : […] un écart total/somme des inters **> 2 %** pose un
> discret marqueur sur la ligne.

Le seuil de 2 % n'était adossé à aucune mesure. Le sondage l'a vérifié avant de le coder.

## Méthode

Pour chaque participation, on reconstitue le calcul que ferait l'écran :

- on écarte les **relais** (la somme des inters d'un relayeur n'a pas le même sens) ;
- on écarte les lignes **sans splits** ;
- on applique le schéma de segments du sport (`frontend/lib/utils/splits.ts` :
  triathlon `swim/t1/bike/t2/run`, duathlon `course1/t1/bike/t2/course2`, aquathlon
  `swim/run`, aquarun `swim/t1/run`, bike-run `bike/run`) et on écarte les lignes dont
  **un segment du schéma manque** ;
- on écarte les lignes dont le total ou l'un des inters n'est **pas lisible comme une
  durée** (même analyseur que `secondsFromHms`) ;
- sur ce qui reste, on calcule `écart = (total − Σ inters) / total`.

**4 150 lignes évaluables** sur 11 629, réparties sur 25 épreuves. Les exclusions :
3 254 schéma incomplet, 3 123 sans splits, 1 041 relais, 37 total illisible, 24 un inter
illisible.

Scripts du sondage : `sondage_ecart{,2,3,4}.py`, joints au scratchpad de la session. Ils
lisent la base en lecture seule et ne dépendent d'aucun code applicatif — c'est
volontaire : ils mesurent la donnée, pas l'implémentation.

## Mesure 1 — la règle proposée signalerait 8 % du classement

| Seuil (écart absolu) | Lignes signalées | Part des évaluées |
| --- | --- | --- |
| **> 2 %** *(proposé)* | **333** | **8,02 %** |
| > 5 % | 22 | 0,53 % |
| > 10 % | 8 | 0,19 % |

**285 des 333 lignes signalées appartiennent à une seule épreuve** — la 47, *Bayman -
Triathlon du Mont Saint-Michel*, que le produit tient par ailleurs pour **fiable**
(`is_reliable_computed = 1`). Un marqueur sur deux lignes sur cinq d'un classement de 681
finishers n'est plus un signal : c'est du bruit, et il salit une épreuve saine.

## Mesure 2 — l'écart est structurel à l'épreuve, pas propre à la ligne

Deux faits le montrent.

**Le signe.** 81,7 % des écarts sont « total > somme », contre 17,3 % dans l'autre sens.
Un écart positif systématique n'est pas une erreur de chronométrage : c'est **un segment
que le chronométreur ne publie pas**. L'exemple le plus net est l'aquathlon — le schéma
`aquathlon` vaut `swim/run`, sans T1, alors que la course en comporte une : la transition
manquante se retrouve intégralement dans l'écart.

**La concentration.** Cinq épreuves sur vingt-cinq portent une médiane d'écart
significative, et sur deux d'entre elles **100 % des lignes** s'écartent du même ordre :

| Épreuve | Médiane d'écart | Lignes évaluées | Nom |
| --- | --- | --- | --- |
| c65 | **+11,44 %** | 9 | Aquathlon des 2 amants — Course 6-9 ans |
| c66 | **+7,44 %** | 13 | Aquathlon des 2 amants — Course 8-11 |
| c61 | +2,10 % | 37 | Aquathlon des 2 amants — Aquathlon S |
| c47 | +1,69 % | 681 | Bayman - Triathlon du Mont Saint-Michel |
| c63 | +1,67 % | 2 | Aquathlon des 2 amants — Aquathlon XS |

Signaler treize fois, sur treize lignes, que la transition n'est pas publiée revient à
répéter treize fois la même phrase. **L'information est vraie au niveau de l'épreuve.**

**La distribution le confirme, et elle est bimodale** : la médiane de l'écart absolu vaut
**3 s**, le troisième quartile **4 s**, puis la valeur saute à **143 s** au 90ᵉ centile.
Il n'y a pas de continuum entre « arrondi de chronométrage » et « segment entier
manquant » — donc pas de seuil relatif unique qui sépare proprement les deux.

## Mesure 3 — aucun plancher absolu ne sauve la règle de la ligne

On a croisé le seuil relatif avec un plancher en secondes, pour voir si la course de
gamins à 5 minutes de total cessait de peser :

| | > 0 s | > 60 s | > 300 s | > 600 s |
| --- | --- | --- | --- | --- |
| > 1 % | 12,9 % | 11,8 % | 4,5 % | 0,0 % |
| > 2 % | 8,0 % | 7,3 % | 4,5 % | 0,0 % |
| > 5 % | 0,5 % | 0,0 % | 0,0 % | 0,0 % |

Le plancher ne discrimine pas : il fait chuter le taux d'un coup, de 4,5 % à 0 %, entre
300 s et 600 s. C'est cohérent avec la bimodalité — on ne règle pas un curseur, on bascule
d'un mode à l'autre.

## Mesure 4 — la règle qui tient : l'écart **à ses pairs**

Si l'écart est une propriété de l'épreuve, alors une ligne n'est douteuse que quand elle
s'écarte de **ses voisines**. On compare donc l'écart de la ligne à la **médiane des
écarts de son épreuve**.

| Seuil sur `|écart − médiane|` | Toutes épreuves | Épreuves ≥ 10 lignes | ≥ 10 lignes ET > 60 s |
| --- | --- | --- | --- |
| > 2 % | 24 lignes / 4 ép. | 21 / 3 | 21 / 3 |
| > 3 % | 4 / 2 | 1 / 1 | 1 / 1 |
| **> 5 %** | 2 / 1 | **0 / 0** | **0 / 0** |
| > 8 % | 0 / 0 | 0 / 0 | 0 / 0 |

Les deux lignes que le seuil de 5 % retient sans garde d'effectif appartiennent à c65 —
neuf enfants, des totaux de quatre à six minutes, où vingt secondes font 6 % : la médiane
d'une population de neuf n'a pas de sens, et le petit dénominateur fait le reste.

**Retenu : écart à la médiane > 5 %, sur les épreuves d'au moins 10 lignes évaluées, et
au moins 60 s d'écart en valeur absolue.** Sur la base de dev, cette règle signale **0
ligne sur 4 150**.

## Ce que le sondage ne prouve pas

**Zéro ligne signalée, c'est zéro fausse alerte — et aucune preuve de captation.** Le cas
qui a motivé l'entrée `RES-10` n'est pas dans la base de dev : la course 214, dont le
premier affiche 31 s + 34 s + 19 min 18 s pour un total de 1 h 06 min 18 s, soit un écart
de **69,3 % (2 755 s)**. Cet écart passerait la règle retenue tant que la médiane de son
épreuve reste sous 64 % — ce qui est acquis, une épreuve entière ne pouvant pas avoir 64 %
de son temps hors des inters sans que le schéma soit tout simplement faux.

La captation reste donc établie **par le cas de l'audit, pas par la base de dev**. C'est
un angle mort assumé : la base de dev ne contient aucune ligne réellement fausse au sens
de `RES-10`. Il faudra le re-sonder sur la base de production avant de considérer le seuil
comme calibré, et un test unitaire doit figer le cas 214 en fixture pour que la règle ne
puisse pas cesser de le capter sans que la suite le dise.

## Ce que le sondage change dans le lot

1. **Le seuil de 2 % de l'audit est abandonné.** Mesuré, il signale 8 % des lignes, dont
   285 sur une épreuve saine.
2. **Le signal se dédouble.** Au niveau **épreuve**, une médiane d'écart supérieure à 1 %
   dit que les inters publiés ne couvrent pas tout le parcours — 5 épreuves sur 25 dans la
   base de dev. Au niveau **ligne**, seul un écart à la médiane de plus de 5 % (avec les
   deux gardes ci-dessus) pose un marqueur.
3. **La médiane doit venir du serveur.** Elle porte sur l'épreuve entière, or l'écran ne
   reçoit que vingt lignes : la calculer côté client la ferait varier de page en page.
4. **Le calcul de l'écart vit à un seul endroit.** Le front et le back ne peuvent pas
   l'implémenter chacun de son côté sans rejouer #76 — la règle club réimplémentée trois
   fois, et un `%nantais%` qui a compté tout Nantes comme TCN. Le serveur publie l'écart
   par ligne **et** la médiane par épreuve ; l'écran ne fait que comparer à ses seuils
   d'affichage.
