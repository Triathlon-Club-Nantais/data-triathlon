import { redirect } from "next/navigation";
import { NAV, ROLE, estVisible } from "@/components/layout/nav.config";
import { apiServer } from "@/lib/api/server";

/** `/encadrement` n'a pas d'écran propre : il mène au premier écran ouvert (#1297). */
export default async function SupervisionHome() {
  const session = await apiServer.getSession();
  const pouvoirs = new Set(session?.permissions ?? []);
  const items = NAV.filter((s) => s.space === "encadrement").flatMap((s) => s.items);
  const premier = items.find((i) => i.href && estVisible(i, pouvoirs, ROLE.CONNECTED)) ?? items[0];
  redirect(premier.href!);
}
