/**
 * Nom du cookie qui porte la largeur du rail de navigation (#482, NAV-3),
 * partagé entre l'écriture cliente (`AppNav.tsx`), la lecture serveur
 * (`app/layout.tsx`) et le relais de cookies vers le backend
 * (`lib/api/server.ts`, qui l'exclut explicitement). Un seul nom : une faute
 * de frappe dans l'un des trois désynchroniserait silencieusement écriture et
 * lecture.
 */
export const NAV_WIDTH_COOKIE = "tcn-nav-expanded";
