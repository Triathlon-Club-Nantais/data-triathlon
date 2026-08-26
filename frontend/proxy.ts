import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const LOGGED_IN_COOKIE = "tcn_logged_in";

/**
 * En-tête **bloquant** (#570) — fin du constat A05-2 de l'audit OWASP.
 *
 * La phase d'observation de #448 n'était pas une simulation : `Report-Only`
 * injecte déjà le nonce (`app-render.js` lit les deux noms), donc elle
 * rapportait exactement ce que ce nom applique. Le relevé mené sur la preview
 * a sonné trois sources de style ou d'`eval` en ligne, toutes traitées à la
 * source ou épinglées avant cette bascule :
 *
 * - `sonner`, qui injecte sa feuille à l'import → les deux hashes ci-dessous ;
 * - Base UI, qui injecte `.base-ui-disable-scrollbar` au montage de ses popups
 *   → nonce transmis par `CSPProvider` (`app/layout.tsx`) ;
 * - `zod`, qui sonde `new Function("")` pour son JIT → `jitless`
 *   (`components/scrape/ManualResultForm.tsx`).
 *
 * Le rendu serveur, lui, est propre : sur les onze routes relevées, 100 % des
 * `<script>` et le `<link rel="stylesheet">` portent le nonce.
 */
const CSP_HEADER = "Content-Security-Policy";

/**
 * `sonner@2.0.8` injecte sa feuille de style **à l'import**, au niveau module,
 * sans nonce et sans possibilité de s'y opposer (`dist/index.mjs`, `__insertCSS`) :
 *
 * ```js
 * let style = document.createElement('style')
 * head.appendChild(style)                                  // ← <style> encore vide
 * style.appendChild(document.createTextNode(code))         // ← puis le CSS
 * ```
 *
 * Le navigateur évalue les deux temps, d'où deux hashes : celui de la chaîne
 * vide, constant, et celui du CSS, **qui dérive à chaque montée de version**.
 * `proxy.test.ts` les recalcule depuis `node_modules/sonner/dist/index.mjs` et
 * échoue si l'un des deux dérive — sans quoi les toasts perdraient tout leur
 * style, silencieusement, en production.
 *
 * Ajouter `'unsafe-inline'` à `style-src` ne serait pas une sortie : CSP niveau
 * 3 impose au navigateur de l'ignorer dès qu'un nonce ou un hash est présent
 * dans la même directive.
 */
const HASHES_STYLE_SONNER = [
  "'sha256-47DEQpj8HBSa+/TImW+5JCeuQeRkm5NMpJWZG3hSuFU='",
  "'sha256-StEaX+se6YS7pqjzrzMIA0KaX9zF/8zAhvQXZAe5epY='",
];

/**
 * Politique de sécurité du contenu (#448, constat A05-2 de l'audit OWASP).
 *
 * Fonction **pure** : le nonce et le mode lui sont passés, ce qui la rend
 * testable sans requête. Toute la politique vit ici, et nulle part ailleurs —
 * deux en-têtes CSP sur une même réponse se cumulent **par intersection**,
 * chacun évalué séparément, donc la scinder entre `next.config.ts` et ce
 * fichier donnerait deux sources de vérité et des rapports en double.
 *
 * `script-src` est la **première** directive dont le nom commence par
 * `script-src` : Next cherche la sienne par `startsWith`, donc une future
 * `script-src-elem` placée avant lui volerait la recherche et le nonce ne
 * serait plus injecté.
 */
export function buildCspPolicy(nonce: string, { dev }: { dev: boolean }): string {
  return [
    "default-src 'self'",
    // `'strict-dynamic'` rend les listes d'origines inopérantes pour les
    // scripts : un script inséré par un script de confiance est autorisé par
    // propagation. C'est le cas d'`array.js`, que `posthog-js` insère lui-même
    // — rien à énumérer — et cela ferme la classe de contournement par liste
    // blanche. `'unsafe-eval'` : React s'en sert en développement seulement,
    // pour reconstruire les piles d'erreurs serveur dans le navigateur.
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${dev ? " 'unsafe-eval'" : ""}`,
    `style-src 'self' 'nonce-${nonce}' ${HASHES_STYLE_SONNER.join(" ")}`,
    // La seule concession, et elle est bornée aux **attributs** : un nonce ne
    // s'applique jamais à un attribut `style`, et le front en porte 412.
    // Écrire `style-src 'unsafe-inline'` à la place ouvrirait aussi les
    // éléments `<style>` et les feuilles. **Assumée comme définitive** (#570) :
    // la retirer supposerait de supprimer les 412 attributs du front, chantier
    // sans rapport avec la politique elle-même.
    "style-src-attr 'unsafe-inline'",
    // Les deux seules origines tierces du front, toutes deux des images : les
    // tuiles de la carte et les trois marqueurs Leaflet servis par unpkg.
    // `data:` couvre les SVG inlinés par Tailwind ; pas de `blob:`, rien ne
    // crée d'URL d'objet.
    "img-src 'self' data: https://*.tile.openstreetmap.org https://unpkg.com",
    // Polices Anton/Barlow auto-hébergées au build par `next/font/google`.
    "font-src 'self'",
    // Tout le trafic navigateur est même-origine : `/api/v1` en relatif, et
    // PostHog derrière le proxy inverse `/ingest` de #396. Retirer ce rewrite
    // bloquerait donc les événements — en mode bloquant seulement.
    "connect-src 'self'",
    "object-src 'none'",
    // Aucune `iframe` dans le front, dans un sens comme dans l'autre.
    "frame-src 'none'",
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    // Servi en clair en développement, où la promotion casserait toutes les
    // sous-ressources.
    ...(dev ? [] : ["upgrade-insecure-requests"]),
  ].join("; ");
}

/**
 * Auto-guérison du cookie de présence (#427).
 *
 * `useSession` saute `GET /auth/me` quand `tcn_logged_in` est absent — sans
 * quoi ce 401, correct par conception pour un anonyme, s'affichait en rouge
 * dans la console de **tout** visiteur, l'immense majorité étant anonyme.
 * Mais un visiteur déjà connecté **avant** ce correctif porte `tcn_session`
 * sans encore porter `tcn_logged_in` : sans cette auto-guérison, il serait vu
 * comme anonyme jusqu'à sa prochaine connexion ou l'expiration de sa session
 * (7 jours, sans prolongation glissante). `endsWith` couvre `tcn_session`
 * (dev) et `__Host-tcn_session` (production) sans dupliquer la dérivation du
 * préfixe, propre au backend (`app/api/v1/auth.py`).
 */
function markSessionPresence(request: NextRequest, response: NextResponse): void {
  const porteUneSession = request.cookies
    .getAll()
    .some((cookie) => cookie.name.endsWith("tcn_session"));

  if (!porteUneSession || request.cookies.has(LOGGED_IN_COOKIE)) return;

  response.cookies.set(LOGGED_IN_COOKIE, "1", {
    path: "/",
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
  });
}

/**
 * La CSP est le **tronc** de ce proxy, le marquage de présence un effet de bord
 * sur la réponse : les sorties précoces de #427 court-circuitaient sinon la
 * politique pour la majorité des visiteurs.
 */
export function proxy(request: NextRequest) {
  const nonce = Buffer.from(crypto.randomUUID()).toString("base64");
  const policy = buildCspPolicy(nonce, {
    dev: process.env.NODE_ENV === "development",
  });

  // Posée sur la **requête** transmise au renderer, pas seulement sur la
  // réponse : c'est là que Next lit le nonce. N'écrire que la réponse donnerait
  // une politique correcte et un HTML sans nonce, donc un rapport de violations
  // sur les propres scripts de Next.
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set(CSP_HEADER, policy);

  const response = NextResponse.next({ request: { headers: requestHeaders } });
  response.headers.set(CSP_HEADER, policy);

  markSessionPresence(request, response);
  return response;
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
