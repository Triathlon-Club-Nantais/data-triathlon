import { z } from "zod";

// #570 : zod sonde `new Function("")` dès la construction d'un schéma objet
// (`z.object(...)`, donc au chargement du module qui le déclare) pour activer
// sa compilation JIT. Sous CSP stricte, le navigateur rapporte la sonde en
// violation `script-src eval`, alors même que zod rattrape l'échec. `jitless`
// court-circuite la sonde sans rien coûter : sans `'unsafe-eval'`, le JIT
// n'aurait jamais servi. Tout le front importe `z` d'ici, jamais de "zod"
// (`lib/zod.test.ts`), pour que la config précède toujours le premier schéma.
z.config({ jitless: true });

export { z };
