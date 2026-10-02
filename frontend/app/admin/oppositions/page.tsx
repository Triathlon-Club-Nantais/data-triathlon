import type { Metadata } from "next";
import { PageHeader } from "@/components/layout/PageHeader";
import { ecran } from "@/components/layout/nav.config";
import { PageShell } from "@/components/layout/PageShell";
import { OppositionsScreen } from "@/components/admin/OppositionsScreen";

export const metadata: Metadata = { title: ecran("/admin/oppositions").title };

export default function AdminOppositionsPage() {
  return (
    <PageShell>
      <div className="space-y-6">
        <PageHeader {...ecran("/admin/oppositions")} />
        <OppositionsScreen />
      </div>
    </PageShell>
  );
}
