import { ImageResponse } from "next/og";
import { getFaviconColor } from "@/lib/favicon";

export const size = { width: 32, height: 32 };
export const contentType = "image/png";

// Marque graphique extraite du logo officiel du club (triangle abstrait,
// hors du texte "TRIATHLON CLUB NANTAIS" — trop large pour un favicon carré).
// Source : https://triathlon-club-nantais.com/wp-content/uploads/2022/11/logo-couleur.svg
//
// Cette icône dynamique gère la différenciation prod/preview via <link
// rel="icon">, lue par les navigateurs modernes. app/favicon.ico reste
// présent en complément, statique et toujours orange (prod) : certains
// navigateurs/crawlers requêtent /favicon.ico directement, sans lire le
// <link>, et perdraient toute icône si ce fichier disparaissait.
const MARK_PATH =
  "M33.79 53.04c-17.34-3.66-31.66-5.32-32.01-3.72-.34 1.6 13.45 5.87 30.78 9.52 17.34 3.66 31.68 5.32 32.01 3.72.34-1.6-13.44-5.86-30.78-9.52m-9.12-27.6C37.08 12.79 46.19 1.6 45.02.45 43.85-.69 32.85 8.63 20.43 21.29 8.04 33.95-1.07 45.14.1 46.29c1.16 1.14 12.17-8.19 24.57-20.84M62 29.43C56.28 12.65 50.38-.51 48.83.02c-1.55.53 1.83 14.55 7.56 31.33 5.72 16.77 11.62 29.94 13.17 29.41 1.56-.53-1.84-14.56-7.55-31.33";

// viewBox légèrement plus large que la bbox réelle du chemin (0,0 → 70,63.25) :
// une marge trop juste rognait la pointe droite du triangle (revue #665).

export default function Icon() {
  const color = getFaviconColor(process.env.FAVICON_VARIANT);

  return new ImageResponse(
    (
      <svg width={32} height={32} viewBox="-2 -2 74 67.25" xmlns="http://www.w3.org/2000/svg">
        <path fill={color} fillRule="evenodd" d={MARK_PATH} />
      </svg>
    ),
    { ...size }
  );
}
