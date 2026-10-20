"use client";

import { useQuery } from "@tanstack/react-query";
import { Card, Eyebrow } from "@/components/tcn";
import { apiClient } from "@/lib/api/client";
import { motCompte } from "@/lib/utils/format";

const LARGEUR = 240;
const HAUTEUR = 160;
const MARGE = 16;

// Projection équirectangulaire recadrée sur mes épreuves. Une carte à tuiles
// (MapView) ferait charger Leaflet pour une vignette de quelques points.
function projeter(points: { lat: number; lon: number }[]) {
  const lats = points.map((p) => p.lat);
  const lons = points.map((p) => p.lon);
  const [latMin, latMax, lonMin, lonMax] = [Math.min(...lats), Math.max(...lats), Math.min(...lons), Math.max(...lons)];
  const echelleLon = Math.cos((((latMin + latMax) / 2) * Math.PI) / 180);
  const etendueX = (lonMax - lonMin) * echelleLon;
  const etendueY = latMax - latMin;
  const echelle = Math.min(
    etendueX > 0 ? (LARGEUR - 2 * MARGE) / etendueX : Infinity,
    etendueY > 0 ? (HAUTEUR - 2 * MARGE) / etendueY : Infinity,
  );
  const [centreX, centreY] = [LARGEUR / 2, HAUTEUR / 2];
  return (p: { lat: number; lon: number }) => ({
    x: Number.isFinite(echelle) ? centreX + ((p.lon - (lonMin + lonMax) / 2) * echelleLon) * echelle : centreX,
    y: Number.isFinite(echelle) ? centreY - (p.lat - (latMin + latMax) / 2) * echelle : centreY,
  });
}

/** Petite carte des lieux de mes épreuves (#1701), masquée si aucune n'est géolocalisée. */
export function MiniCarte({ courseIds }: { courseIds: number[] }) {
  const geo = useQuery({
    queryKey: ["mon-espace", "events-geo"],
    queryFn: () => apiClient.getEventsGeo(),
    retry: false,
  });

  const miens = new Set(courseIds);
  const lieux = (geo.data ?? []).filter((e) => miens.has(e.course_id));
  if (lieux.length === 0) return null;
  const placer = projeter(lieux);
  const noms = [...new Set(lieux.map((e) => e.event_name))];

  return (
    <Card padding={20}>
      <Eyebrow>Carte de mes épreuves</Eyebrow>
      <svg
        role="img"
        aria-label={`Carte de ${motCompte(lieux.length, "épreuve")}, détail dans la liste des lieux`}
        viewBox={`0 0 ${LARGEUR} ${HAUTEUR}`}
        style={{ marginTop: 12, width: "100%", height: "auto", background: "var(--tcn-orange-08)", borderRadius: 8 }}
      >
        {lieux.map((e) => {
          const { x, y } = placer(e);
          return <circle key={e.course_id} cx={x} cy={y} r={6} fill="var(--tcn-orange)" stroke="var(--tcn-ink)" strokeWidth={1.5} />;
        })}
      </svg>
      <ul className="sr-only">
        {noms.map((nom) => (
          <li key={nom}>{nom}</li>
        ))}
      </ul>
    </Card>
  );
}
