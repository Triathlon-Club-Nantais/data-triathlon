import type { Metadata } from "next";
import { PageHeader } from "@/components/layout/PageHeader";
import { ecran } from "@/components/layout/nav.config";
import { PageShell } from "@/components/layout/PageShell";
import { IgnoredCourseDuplicates } from "@/components/admin/ArbitrationUndoList";
import { CourseDuplicatesTable } from "@/components/admin/CourseDuplicatesTable";

export const metadata: Metadata = { title: ecran("/admin/doublons").title };

export default function CourseDuplicatesPage() {
  return (
    <PageShell>
      <div className="space-y-6">
        <PageHeader {...ecran("/admin/doublons")} />
        <CourseDuplicatesTable />
        <IgnoredCourseDuplicates />
      </div>
    </PageShell>
  );
}
