import type { Metadata } from "next";
import { AccountPage } from "@/components/auth/AccountPage";
import { PageHeader } from "@/components/layout/PageHeader";
import { PageShell } from "@/components/layout/PageShell";

export const metadata: Metadata = { title: "Mon compte" };

export default function MonComptePage() {
  return (
    <PageShell form>
      <PageHeader eyebrow="Compte" title="Mon compte" className="mb-6" />
      <AccountPage />
    </PageShell>
  );
}
