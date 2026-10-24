# Sondage : violations CSP réelles en production (#570)

Date : 2026-10-24. Lecture seule : aucune modification de la CSP, du code ni de
Render. Cible : la CSP `Report-Only` posée par `frontend/proxy.ts` sur
`https://data.triathlon-club-nantais.com/`, et les logs Render du service
`triathlon-backend-production` (`srv-d8ssck6q1p3s738mh8g0`), où
`backend/app/services/csp_report.py` écrit une ligne `CSP violation ...` par
rapport reçu.

## Conclusion

1. **Zéro violation CSP réelle en production sur la fenêtre lisible**, du
   2026-10-17 09:34 UTC au 2026-10-24 : ni ligne `CSP violation`, ni même un
   seul `POST /api/v1/csp-reports`.
2. **La fenêtre demandée (depuis le 09/10) n'est pas lisible en entier** : la
   rétention des logs Render du plan gratuit est de 7 jours. Du 09/10 au 17/10,
   seul reste le relevé du 09/10 consigné sur l'issue (aucune violation depuis
   le 06/10).
3. **L'hypothèse de l'issue est dépassée** : le composant qui rend le `<style>`
   hissé par React DOM était déjà identifié et corrigé par la PR #1286 (fusionnée
   le 10/10, en production depuis `v0.8.7`), que les commentaires de l'issue ne
   citent pas. C'est le `<style href precedence>` de Base UI
   (`.base-ui-disable-scrollbar`), signé d'un nonce neuf après
   `router.refresh()`. Le build actuel le confirme : c'est le **seul** `<style>`
   à `precedence` du bundle, et il porte le nonce figé par `StableCSPProvider`.
4. **Rien de mesuré ne bloque la bascule.** Un seul préalable reste ouvert : un
   témoin positif de la chaîne de rapport en production sur la fenêtre, que ce
   sondage n'a pas pu poser (voir « Angle mort »).

## Mesures

### En-têtes servis en production

```console
$ curl -sS -D - -o /dev/null https://data.triathlon-club-nantais.com/ | grep -iE "^(HTTP|content-security|reporting|date)"
HTTP/2 200
content-security-policy-report-only: default-src 'self'; script-src 'self' 'nonce-…' 'strict-dynamic'; style-src 'self' 'nonce-…' 'sha256-47DEQpj8HBSa+/TImW+5JCeuQeRkm5NMpJWZG3hSuFU=' 'sha256-StEaX+se6YS7pqjzrzMIA0KaX9zF/8zAhvQXZAe5epY='; style-src-attr 'unsafe-inline'; img-src 'self' data: https://*.tile.openstreetmap.org https://unpkg.com; font-src 'self'; connect-src 'self'; object-src 'none'; frame-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; upgrade-insecure-requests; report-to csp-endpoint; report-uri /api/v1/csp-reports
date: Sat, 24 Oct 2026 11:23:39 GMT
reporting-endpoints: csp-endpoint="/api/v1/csp-reports"
```

Politique identique à `buildCspPolicy` de `main`, toujours en `Report-Only`.

### Logs Render (outil MCP `list_logs`, lecture seule)

| Requête | Fenêtre (UTC) | Résultat |
| --- | --- | --- |
| `text: "CSP violation"` | 09/10 00:00 → 24/10 23:59 | **0 ligne** |
| `text: "CSP violation"` (témoin : les deux violations connues du 05/10 et 06/10) | 25/09 → 09/10 | 0 ligne : hors rétention |
| sans filtre, `direction: forward`, `limit: 3` sur 25/09 → 24/10 | | plus ancien log : **2026-10-17T09:34:06Z** |
| `text: "*CSP*"` puis `text: "csp-reports"` | 17/10 → 24/10 | 1 seule ligne : `GET /api/v1/csp-reports` → 405, le 19/10 12:57, depuis `51.195.199.91` (sonde, pas un navigateur) |
| `path: "/api/v1/csp-reports"` | 25/09 → 24/10 | 0 : le service n'a pas de logs de type `request` (`list_log_label_values type` → `app`, `build`), l'accès passe par les lignes uvicorn |

uvicorn journalise **toutes** les réponses, y compris un 403 de
`OriginGuardMiddleware` ou un 413 de taille : zéro ligne `POST /api/v1/csp-reports`
signifie qu'aucun rapport n'a atteint le backend, accepté ou refusé.

Groupement par directive et source : **vide** sur la fenêtre. Pour mémoire,
l'historique complet de la production depuis la MEP v0.8.0, relevé sur l'issue :

| Date | Directive | Source | Page | Cause |
| --- | --- | --- | --- | --- |
| 05/10 14:13 | `style-src-elem`, `blocked=inline` | `/_next/static/chunks/3vk4o7wc3zljr.js:31` (React DOM) | `/courses/1028` | Base UI après `router.refresh()`, corrigé par #1286 |
| 06/10 12:06 | idem | idem | `/athletes/36695` | idem |

### Le trafic réel a bien parcouru les chemins à risque

Le zéro ne vient pas d'une absence de visiteurs. Écritures relevées sur la
fenêtre (`text: "*POST /api/v1/*"` puis les écritures admin), IP de visiteurs
résidentiels relayées par le front :

- `POST /api/v1/site-access/session` → 204 les 18/10 (×3) et 21/10 :
  `SiteAccessGate` enchaîne sur `router.refresh()`, le mécanisme même des
  violations d'octobre ;
- `POST /api/v1/scrape/event/stream` → 200 les 18/10 et 19/10 : import depuis
  `/ajouter`, suivi d'un `router.refresh()` par `ImportStreamProvider` ;
- gestes admin à toast `sonner` : imports d'adhérents (19/10, 22/10),
  4 `PATCH /admin/feedback` (19/10), approbations de demande de membre et de
  rattachement d'athlète, suppression d'adresse (22/10).

**Non parcouru** : aucun geste d'admin sur une fiche épreuve ou athlète
(`CourseAdminPanel`, `AthleteAdminPanel`, fusion, détachement), le scénario
exact des 05/10 et 06/10.

### Attribution du `<style>` hissé par React DOM

Le chunk cité par l'issue n'existe plus (`GET /_next/static/chunks/3vk4o7wc3zljr.js`
→ 404). Dans les 22 chunks de la page d'accueil de production, le code React DOM
de hissage est dans `1ebmqts7ymq3f.js`, **toujours ligne 31** :

```js
…querySelector('style[data-href~="'+ty(n.href)+'"]');…var l=_({},n,{"data-href":n.href,"data-precedence":n.precedence,href:null,precedence:null});return e7(r=(e.ownerDocument||e).createElement("style")),…
```

Build local de `main` (`d1e01199`, `next@16.4.0`, `react-dom@19.3.0`,
`@base-ui/react@1.8.0`, `sonner@2.0.8`) : `npm ci && npm run build`, compilé et
48 pages générées (Next sort ensuite en code 1 sur un avis de sécurité de
`next@16.4.0`, sans effet sur les chunks). Recherche dans
`frontend/.next/static/chunks` :

```console
$ grep -c 'createElement("style")' *.js | grep -v ':0'
2mt6vi9p_8-8o.js:1      # sonner, __insertCSS (couvert par les deux hashes)
2pyzn5dhmeldh.js:1      # React DOM, hissage des ressources de style (ligne 31)
$ grep -o 'precedence:"[^"]*"' *.js | sort | uniq -c
      1 21c205s2djcc9.js:precedence:"dynamic"      # <link rel=stylesheet> de Next, nonce + 'self'
      1 2epm04khuu7k1.js:precedence:"base-ui:low"  # le seul <style> à precedence
$ grep -o '.\{60\}precedence:"base-ui:low".\{20\}' 2epm04khuu7k1.js
ment,{children:[!I&&(l=A,(0,t.jsx)("style",{nonce:l,href:e$,precedence:"base-ui:low",children:`.${e$}{sc
```

La source est `node_modules/@base-ui/react/utils/styles.mjs`
(`styleDisableScrollbar.getElement(nonce)`), utilisé par `ScrollArea` et
`Select` (`SelectPopup`, `SelectList`). Le chunk `2epm04khuu7k1.js` est chargé par
`/courses/[id]`, `/athletes/[id]`, `/resultats`, `/mon-espace` et six écrans
`/admin` : les deux pages des violations d'octobre en font partie.
`StoreInspector` de `@base-ui/utils` (autre `precedence` dans `node_modules`)
est absent du bundle.

Mécanisme, établi par #1286 et toujours valable : `router.refresh()` rejoue le
layout racine avec le nonce d'une **nouvelle** requête, alors que la CSP du
document garde celui du chargement. `StableCSPProvider`
(`frontend/components/layout/StableCSPProvider.tsx`) fige le nonce au premier
rendu ; il est monté dans le layout racine, donc survit au refresh.

## Ce qui bloque la bascule, et la plus petite correction

| Cause | État | Plus petite correction |
| --- | --- | --- |
| Base UI, `<style precedence>` signé d'un nonce neuf après `router.refresh()` | corrigé (#1286, `v0.8.7`) ; 0 violation depuis | rien |
| `sonner`, feuille injectée à l'import | deux hashes épinglés, `proxy.test.ts` échoue à la dérive | rien |
| `zod`, sonde `new Function("")` | `jitless` (`lib/zod.ts`) | rien |
| Témoin positif de la chaîne de rapport en production sur la fenêtre | non posé (refusé par le garde-fou de session, écriture en prod) | un `POST` de test, puis lecture de sa ligne dans les logs Render dans les 7 jours |

La bascule elle-même reste ce que #570 prévoit : `CSP_HEADER =
"Content-Security-Policy"` dans `frontend/proxy.ts`, commentaires et test
ajustés. `upgrade-insecure-requests`, ignoré en `Report-Only`, deviendra actif :
tout est déjà servi en HTTPS.

## Angle mort

**Le zéro n'a pas de témoin positif sur la fenêtre.** Le dernier témoin en
production date du 05/10 (`test-recette-mep`). Depuis, la chaîne a été touchée
(#1553, le 16/10, fait passer tout `/api/*` par `forwardToBackend` dans
`proxy.ts` pour y poser le secret de #1533) ; les autres `POST /api/v1/*` du trafic réel la traversent bien, mais
aucun rapport CSP ne l'a prouvée. Ce sondage a tenté le témoin (rapport de test
`test-570-sondage`), refusé par le garde-fou de la session comme écriture en
production. À faire à la main avant la PR de bascule :

```sh
curl -sS -o /dev/null -w "%{http_code}\n" -X POST \
  https://data.triathlon-club-nantais.com/api/v1/csp-reports \
  -H 'Content-Type: application/csp-report' \
  --data '{"csp-report":{"effective-directive":"test-570-sondage","blocked-uri":"inline","document-uri":"https://data.triathlon-club-nantais.com/","source-file":"curl","line-number":0,"disposition":"report"}}'
# attendu : 204, puis une ligne "CSP violation directive=test-570-sondage" dans list_logs
```

Rétention : les logs Render ne gardent que 7 jours, toute observation de suite
doit être lue dans ce délai.
