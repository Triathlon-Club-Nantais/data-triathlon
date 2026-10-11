# Audit du keep-warm Azure (#1315)

Mesuré le 11/10/2026 sur App Insights `coldstart-curl`, fenêtre glissante de 7 jours (04/10 13:30 → 11/10 13:20 UTC).

## Mesures

**Invocations.** 714 exécutions de `Coldstart-curl`, 102 par jour pleine (17 h × 6, conforme au timer `0 */10 7-23 * * *`), toutes en *Succeeded*. Durée p50 ~6,1 s, p95 ~7,8 s, max 10,7 s.

**Ce que *Succeeded* cache.** Comme pour `Render-*` (#1320), une erreur HTTP d'`Invoke-RestMethod` n'arrête que l'appel : l'invocation reste verte. Les exceptions journalisées :

| URL appelée | Timeout client 1 s | 502 | Appels | Taux d'échec |
|---|---|---|---|---|
| production `data.triathlon-club-nantais.com` | 291 | 18 | 714 | 43 % |
| preview `data-triathlon-tcn-preview.vercel.app` | 687 | 13 | 714 | 98 % |

Aucun 401 ni 503 : `CRON_SECRET` est aligné entre Azure et les deux projets Vercel.

**Les timeouts.** `-ConnectionTimeoutSeconds 1` règle en PowerShell 7.4 le `HttpClient.Timeout` de **toute** la requête, pas seulement la connexion. La route attend la réponse de `/api/v1/health` (jusqu'à 10 s) avant de répondre : dès que l'aller-retour Vercel → Render dépasse 1 s, Azure abandonne. Le `fetch` vers le backend part dans les premières millisecondes de la route, donc le ping a très probablement lieu quand même ; on perd seulement la visibilité sur son résultat.

**Les 502 de la production** tombent tous dans deux créneaux attendus :

- 23:20 → 23:50 UTC les 05, 06 et 07/10 : la production est couchée à 23:15, le keep-warm tourne jusqu'à 23:50 ;
- 07:10 → 08:40 UTC le 11/10 : lever retardé par la panne du jeton (#1317).

Hors de ces créneaux, aucun 502 : le backend de production a répondu à chaque ping dont on connaît l'issue.

**La preview.** Son backend est suspendu chaque heure par `render-sleep.yml` et ne se rallume qu'au déploiement : le keep-warm ne peut pas la réveiller (une suspension Render n'est pas un sommeil d'inactivité), et 98 % de ses appels échouent.

## Non mesuré

- Les cold starts réels vus par un visiteur : la route ne journalise `durationMs` que sur échec, et App Insights ne voit que le client Azure. Le seul indice disponible (aucun 502 hors créneaux attendus) va dans le sens d'un backend tenu éveillé.

## Conclusion

Le keep-warm **fonctionne** pour la production : secret valide, backend joint à chaque créneau d'usage. Il est en revanche **aveugle** (43 % d'appels coupés côté client, invocations toujours vertes) et **inutile pour la preview**. Correctifs suivis dans #1333 : timeout client au-dessus de celui de la route, échec visible de l'invocation, retrait de l'URL preview, dernier appel à 22 h 50 UTC au lieu de 23 h 50.
