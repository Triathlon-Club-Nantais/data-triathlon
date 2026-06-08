import { cookies } from "next/headers";

export { CLUB_COOKIE, TCN_CLUB_FILTER } from "./club-constants";

/** true si le filtre « membres TCN uniquement » est actif (lu côté RSC). */
export async function isClubFilterActive(): Promise<boolean> {
  const store = await cookies();
  return store.get("tcn-only")?.value === "1";
}
