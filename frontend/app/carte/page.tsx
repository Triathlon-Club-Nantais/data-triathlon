"use client";
import dynamic from "next/dynamic";
import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { PageHeader } from "@/components/layout/PageHeader";
import { PageShell } from "@/components/layout/PageShell";
import { ScopeToggle } from "@/components/layout/ScopeToggle";
import { clubFromScope } from "@/lib/scope";

const MapView = dynamic(() => import("@/components/map/MapView").then((m) => m.MapView), {
  ssr: false,
  loading: () => (
    <p className="py-10 text-center text-muted-foreground">Chargement de la carte…</p>
  ),
});

function CarteContent() {
  const sp = useSearchParams();
  const club = clubFromScope(sp.get("scope"));
  return (
    <PageShell>
      <div className="space-y-6">
        <PageHeader
          eyebrow="Géographie des épreuves"
          title="Carte des épreuves"
          description="Localisation des épreuves importées. La taille des cercles reflète le nombre de participants."
          actions={<ScopeToggle />}
        />
        <MapView club={club} />
        <div className="flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
          <span className="inline-flex items-center gap-1.5">
            <span className="inline-block size-3 rounded-full bg-[#E9530E]" />
            Épreuve avec des membres TCN
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="inline-block size-3 rounded-full bg-[#b0aaa0]" />
            Épreuve sans membre TCN
          </span>
        </div>
      </div>
    </PageShell>
  );
}

export default function CartePage() {
  return (
    <Suspense
      fallback={
        <p className="py-10 text-center text-muted-foreground">Chargement…</p>
      }
    >
      <CarteContent />
    </Suspense>
  );
}
