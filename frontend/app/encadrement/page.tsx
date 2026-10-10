import { redirect } from "next/navigation";
import { NAV, ROLE, estVisible } from "@/components/layout/nav.config";
import { apiServer } from "@/lib/api/server";

/** `/encadrement` n'a pas d'écran propre : il mène au premier écran ouvert (#1297). */
export default async function SupervisionHome() {
  // Backend injoignable : le layout laisse passer, la page retombe sur le premier écran.
  const session = await apiServer.getSession().catch(() => null);
  const pouvoirs = new Set(session?.permissions ?? []);
  const items = NAV.filter((s) => s.space === "encadrement").flatMap((s) => s.items);
  const ouvert = items.find((i) => estVisible(i, pouvoirs, ROLE.CONNECTED));
  redirect((ouvert ?? items[0]).href ?? "/");
}
