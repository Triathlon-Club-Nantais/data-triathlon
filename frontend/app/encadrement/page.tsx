import { redirect } from "next/navigation";
import { NoAdminAccess } from "@/components/admin/NoAdminAccess";
import { NAV, ROLE, estVisible } from "@/components/layout/nav.config";
import { PageHeader } from "@/components/layout/PageHeader";
import { PageShell } from "@/components/layout/PageShell";
import { apiServer } from "@/lib/api/server";

/** `/encadrement` n'a pas d'écran propre : il mène au premier écran ouvert (#1297). */
export default async function SupervisionHome() {
  // Backend injoignable : le layout laisse passer, la page retombe sur le premier écran.
  const session = await apiServer.getSession().catch(() => null);
  const items = NAV.filter((s) => s.space === "encadrement").flatMap((s) => s.items);
  if (!session) redirect(items[0].href ?? "/");

  const pouvoirs = new Set(session.permissions);
  const ouvert = items.find((i) => estVisible(i, pouvoirs, ROLE.CONNECTED));
  if (ouvert) redirect(ouvert.href);

  return (
    <PageShell>
      <div className="space-y-6">
        <PageHeader title="Encadrement" />
        <NoAdminAccess space="encadrement" />
      </div>
    </PageShell>
  );
}
