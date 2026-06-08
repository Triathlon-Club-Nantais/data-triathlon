import { cookies } from "next/headers";

export const CLUB_COOKIE = "tcn-only";

/** true si le filtre « membres TCN uniquement » est actif (lu côté RSC). */
export async function isClubFilterActive(): Promise<boolean> {
  const store = await cookies();
  return store.get(CLUB_COOKIE)?.value === "1";
}

/** Valeur de filtre club à passer à l'API quand le toggle est actif. */
export const TCN_CLUB_FILTER = "nantais";
