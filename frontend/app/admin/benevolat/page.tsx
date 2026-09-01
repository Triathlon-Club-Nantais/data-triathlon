import { PageHeader } from "@/components/layout/PageHeader";
import { PageShell } from "@/components/layout/PageShell";

/**
 * Reconstruite par #817 (écran de validation des déclarations de crédit
 * d'athlète) dans la même fenêtre de travail que ce retrait (#816,
 * research.md D3) — état minimal temporaire, jamais poussé seul.
 */
export default function AdminBenevolatPage() {
  return (
    <PageShell>
      <div className="space-y-6">
        <PageHeader eyebrow="Bénévolat" title="Bénévolat" description="" />
      </div>
    </PageShell>
  );
}
