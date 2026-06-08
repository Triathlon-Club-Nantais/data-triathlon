import { cookies } from "next/headers";
import { CLUB_COOKIE } from "./club-constants";

export { CLUB_COOKIE, TCN_CLUB_FILTER } from "./club-constants";

/** true si le filtre « membres TCN uniquement » est actif (lu côté RSC). */
export async function isClubFilterActive(): Promise<boolean> {
  const store = await cookies();
  return store.get(CLUB_COOKIE)?.value === "1";
}
