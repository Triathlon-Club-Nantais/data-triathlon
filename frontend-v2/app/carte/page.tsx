"use client";
import dynamic from "next/dynamic";

const MapView = dynamic(() => import("@/components/map/MapView").then((m) => m.MapView), {
  ssr: false,
  loading: () => <p className="py-10 text-center text-muted-foreground">Chargement de la carte…</p>,
});

export default function CartePage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Carte des épreuves</h1>
      <MapView />
    </div>
  );
}
