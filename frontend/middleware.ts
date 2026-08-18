import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const LOGGED_IN_COOKIE = "tcn_logged_in";

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
export function middleware(request: NextRequest) {
  const porteUneSession = request.cookies
    .getAll()
    .some((cookie) => cookie.name.endsWith("tcn_session"));

  if (!porteUneSession || request.cookies.has(LOGGED_IN_COOKIE)) {
    return NextResponse.next();
  }

  const response = NextResponse.next();
  response.cookies.set(LOGGED_IN_COOKIE, "1", {
    path: "/",
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
  });
  return response;
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
