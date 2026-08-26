import type { GeoEvent } from "@/lib/types";

/** Siège du club (Nantes) — point de référence statique du tri par distance (US12, #466). */
export const POINT_REFERENCE = { lat: 47.2184, lon: -1.5536 };

const RAYON_TERRE_KM = 6371;

/** Distance à vol d'oiseau entre deux points (formule haversine), en kilomètres. */
export function distanceKm(a: { lat: number; lon: number }, b: { lat: number; lon: number }): number {
  const toRad = (deg: number) => (deg * Math.PI) / 180;
  const dLat = toRad(b.lat - a.lat);
  const dLon = toRad(b.lon - a.lon);
  const sinLat = Math.sin(dLat / 2);
  const sinLon = Math.sin(dLon / 2);
  const h = sinLat * sinLat + Math.cos(toRad(a.lat)) * Math.cos(toRad(b.lat)) * sinLon * sinLon;
  return RAYON_TERRE_KM * 2 * Math.asin(Math.sqrt(h));
}

/** Ne garde que les épreuves dont la date est strictement postérieure à `reference`. */
export function upcomingEvents(events: GeoEvent[], reference: Date): GeoEvent[] {
  return events.filter((ev) => ev.event_date != null && new Date(ev.event_date) > reference);
}

/** Copie de `events` triée par distance croissante à `reference` (le club par défaut). */
export function sortByDistance(events: GeoEvent[], reference: { lat: number; lon: number } = POINT_REFERENCE): GeoEvent[] {
  return [...events].sort((a, b) => distanceKm(reference, a) - distanceKm(reference, b));
}
