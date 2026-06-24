"use client";
import { useEffect, useState } from "react";
import { MapContainer, TileLayer, CircleMarker, Popup, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { apiClient } from "@/lib/api/client";
import { eventTypeLabel } from "@/lib/constants";
import { formatMonth } from "@/lib/utils/date";
import type { GeoEvent } from "@/lib/types";

// Corrige les chemins d'icônes cassés par les bundlers (icônes via CDN).
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

function FitBounds({ events }: { events: GeoEvent[] }) {
  const map = useMap();
  useEffect(() => {
    if (events.length === 0) return;
    const bounds = L.latLngBounds(events.map((e) => [e.lat, e.lon]));
    map.fitBounds(bounds, { padding: [30, 30], maxZoom: 9 });
  }, [events, map]);
  return null;
}

export function MapView({ club }: { club?: string }) {
  const [events, setEvents] = useState<GeoEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    setError("");
    apiClient
      .getEventsGeo(club)
      .then(setEvents)
      .catch(() => setError("Impossible de charger la carte"))
      .finally(() => setLoading(false));
  }, [club]);

  if (loading) return <p className="py-10 text-center text-muted-foreground">Géolocalisation des courses…</p>;
  if (error) return <p className="py-10 text-center text-destructive">{error}</p>;
  if (events.length === 0)
    return <p className="py-10 text-center text-muted-foreground">Aucune course géolocalisée.</p>;

  const maxCount = Math.max(...events.map((e) => e.count), 1);

  return (
    <MapContainer center={[47.2, -1.5]} zoom={7} scrollWheelZoom={false} className="h-[480px] w-full rounded-md">
      <TileLayer
        attribution='© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        maxZoom={13}
      />
      {events.map((ev, i) => {
        const radius = Math.max(10, Math.min(40, 10 + (ev.count / maxCount) * 30));
        const hasTCN = ev.tcn_count > 0;
        return (
          <CircleMarker
            key={`${ev.event_name}-${i}`}
            center={[ev.lat, ev.lon]}
            radius={radius}
            pathOptions={{
              fillColor: hasTCN ? "#E9530E" : "#b0aaa0",
              color: hasTCN ? "#c04008" : "#857f74",
              weight: hasTCN ? 2 : 1,
              fillOpacity: 0.55,
            }}
          >
            <Popup>
              <div className="min-w-[180px]">
                <b>{ev.event_name}</b>
                {ev.event_type && <div className="text-muted-foreground">{eventTypeLabel(ev.event_type)}</div>}
                {ev.event_date && <div className="text-xs">{formatMonth(ev.event_date.slice(0, 7))}</div>}
                <div>
                  {ev.count} participant{ev.count > 1 ? "s" : ""}
                </div>
                {hasTCN && (
                  <div className="font-semibold text-brand">
                    {ev.tcn_count} membre{ev.tcn_count > 1 ? "s" : ""} TCN
                  </div>
                )}
              </div>
            </Popup>
          </CircleMarker>
        );
      })}
      <FitBounds events={events} />
    </MapContainer>
  );
}
