"use client";
import dynamic from "next/dynamic";
import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { PageHeader } from "@/components/layout/PageHeader";
import { PageShell } from "@/components/layout/PageShell";
import { ScopeToggle } from "@/components/layout/ScopeToggle";
import { scopeFromParam } from "@/lib/scope";
import { CLUB_NAME_SHORT } from "@/lib/club";
import { COULEURS_CARTE, LIBELLE_CHARGEMENT } from "@/components/map/carte";

function Attente() {
  return <p className="py-10 text-center text-[var(--tcn-text-body)]">{LIBELLE_CHARGEMENT}</p>;
}

const MapView = dynamic(() => import("@/components/map/MapView").then((m) => m.MapView), {
  ssr: false,
  loading: Attente,
});

/**
 * Une entrée de légende. Le rond reprend les **mêmes** constantes que les cercles
 * de la carte, et son trait pointillé reprend le repère non coloré : la légende
 * portait sa propre copie des littéraux, dont un (`#b0aaa0`) que `MapView`
 * n'utilisait déjà plus pour le trait (#299).
 */
function Teinte({ role, children }: { role: keyof typeof COULEURS_CARTE; children: React.ReactNode }) {
  const teinte = COULEURS_CARTE[role];
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        aria-hidden="true"
        className="inline-block size-3 rounded-full"
        style={{
          background: teinte.remplissage,
          border: `${teinte.epaisseur}px ${teinte.pointilles ? "dashed" : "solid"} ${teinte.trait}`,
        }}
      />
      {children}
    </span>
  );
}

function CarteContent() {
  const sp = useSearchParams();
  const scope = scopeFromParam(sp.get("scope"));
  return (
    <PageShell>
      <div className="space-y-6">
        <PageHeader
          eyebrow="Géographie des épreuves"
          title="Carte des épreuves"
          description="Localisation des épreuves importées. La taille des cercles reflète le nombre de participants."
          actions={<ScopeToggle />}
        />
        <MapView scope={scope} />
        <div className="flex flex-wrap items-center gap-4 text-xs text-[var(--tcn-text-body)]">
          <Teinte role="avecTcn">Épreuve avec des membres {CLUB_NAME_SHORT} (trait plein)</Teinte>
          <Teinte role="sansTcn">Épreuve sans membre {CLUB_NAME_SHORT} (trait pointillé)</Teinte>
        </div>
      </div>
    </PageShell>
  );
}

export default function CartePage() {
  return (
    <Suspense fallback={<Attente />}>
      <CarteContent />
    </Suspense>
  );
}
