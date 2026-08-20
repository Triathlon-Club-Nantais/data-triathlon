"use client";
import dynamic from "next/dynamic";
import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { PageHeader } from "@/components/layout/PageHeader";
import { PageShell } from "@/components/layout/PageShell";
import { ScopeToggle } from "@/components/layout/ScopeToggle";
import { Skeleton } from "@/components/ui/skeleton";
import { scopeFromParam } from "@/lib/scope";
import { CLUB_NAME_SHORT } from "@/lib/club";
import { COULEURS_CARTE } from "@/components/map/carte";

// Même taille que le conteneur réel de MapView.tsx (`h-[320px] sm:h-[480px]`) :
// sans quoi le remplacement par la vraie carte décale tout ce qui suit.
function AttenteCarte() {
  return <Skeleton className="h-[320px] w-full rounded-md sm:h-[480px]" />;
}

const MapView = dynamic(() => import("@/components/map/MapView").then((m) => m.MapView), {
  ssr: false,
  loading: AttenteCarte,
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

/**
 * Portée de la carte : seul point du composant qui a besoin de
 * `useSearchParams`, donc seul point qui a besoin d'une frontière `Suspense`
 * (exigée par Next pour le bail-out statique). L'isoler ici — plutôt que de
 * l'appeler dans `CartePage` et de faire porter la frontière par toute la
 * page — laisse le titre s'afficher sans attendre quoi que ce soit (#476).
 */
function CarteMap() {
  const sp = useSearchParams();
  const scope = scopeFromParam(sp.get("scope"));
  return <MapView scope={scope} />;
}

export default function CartePage() {
  return (
    <PageShell>
      <div className="space-y-6">
        <PageHeader
          eyebrow="Géographie des épreuves"
          title="Carte des épreuves"
          description="Localisation des épreuves importées. La taille des cercles reflète le nombre de participants."
          actions={
            <Suspense fallback={<Skeleton className="h-9 w-40 rounded-lg" />}>
              <ScopeToggle />
            </Suspense>
          }
        />
        <Suspense fallback={<AttenteCarte />}>
          <CarteMap />
        </Suspense>
        <div className="flex flex-wrap items-center gap-4 text-xs text-[var(--tcn-text-body)]">
          <Teinte role="avecTcn">Épreuve avec des membres {CLUB_NAME_SHORT} (trait plein)</Teinte>
          <Teinte role="sansTcn">Épreuve sans membre {CLUB_NAME_SHORT} (trait pointillé)</Teinte>
        </div>
      </div>
    </PageShell>
  );
}
