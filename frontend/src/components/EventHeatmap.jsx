import { useEffect, useRef, useState } from "react";
import { api } from "../api/client.js";
import { EVENT_TYPE_LABELS } from "../constants.js";

export default function EventHeatmap({ club }) {
  const mapRef   = useRef(null);
  const leafRef  = useRef(null);  // leaflet map instance
  const [events,  setEvents]  = useState([]);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState("");

  // Load geodata
  useEffect(() => {
    setLoading(true);
    setError("");
    api.getEventsGeo(club ? { club } : {})
      .then(setEvents)
      .catch(() => setError("Impossible de charger la carte"))
      .finally(() => setLoading(false));
  }, [club]);

  // Build/update Leaflet map when events change
  useEffect(() => {
    if (loading || error || !events.length || !mapRef.current) return;
    if (typeof window === "undefined") return;

    import("leaflet").then((L) => {
      // Fix default icon paths broken by bundlers
      delete L.Icon.Default.prototype._getIconUrl;
      L.Icon.Default.mergeOptions({
        iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
        iconUrl:       "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
        shadowUrl:     "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
      });

      // Destroy previous instance
      if (leafRef.current) {
        leafRef.current.remove();
        leafRef.current = null;
      }

      const map = L.map(mapRef.current, { zoomControl: true, scrollWheelZoom: false })
        .setView([47.2, -1.5], 7);  // Centered on Loire-Atlantique

      leafRef.current = map;

      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        maxZoom: 13,
      }).addTo(map);

      const maxCount = Math.max(...events.map(e => e.count), 1);

      events.forEach((ev) => {
        const radius = Math.max(10, Math.min(40, 10 + (ev.count / maxCount) * 30));
        const hasTCN = ev.tcn_count > 0;

        const circle = L.circleMarker([ev.lat, ev.lon], {
          radius,
          fillColor:   hasTCN ? "#3b82f6" : "#94a3b8",
          color:       hasTCN ? "#1d4ed8" : "#64748b",
          weight:      hasTCN ? 2 : 1,
          opacity:     0.9,
          fillOpacity: 0.55,
        }).addTo(map);

        const type  = EVENT_TYPE_LABELS[ev.event_type] || ev.event_type || "";
        const date  = ev.event_date ? new Date(ev.event_date).toLocaleDateString("fr-FR", { month: "long", year: "numeric" }) : "";
        const tcnLine = hasTCN ? `<br/><b style="color:#2563eb">${ev.tcn_count} membre${ev.tcn_count > 1 ? "s" : ""} TCN</b>` : "";

        circle.bindPopup(`
          <div style="min-width:180px">
            <b style="font-size:14px">${ev.event_name}</b>
            ${type  ? `<br/><span style="color:#6b7280">${type}</span>` : ""}
            ${date  ? `<br/><span style="color:#9ca3af;font-size:12px">${date}</span>` : ""}
            <br/>${ev.count} participant${ev.count > 1 ? "s" : ""} importé${ev.count > 1 ? "s" : ""}
            ${tcnLine}
          </div>
        `);
      });

      // Fit to markers
      if (events.length > 0) {
        const bounds = L.latLngBounds(events.map(e => [e.lat, e.lon]));
        map.fitBounds(bounds, { padding: [30, 30], maxZoom: 9 });
      }
    });

    return () => {
      if (leafRef.current) { leafRef.current.remove(); leafRef.current = null; }
    };
  }, [events, loading, error]);

  return (
    <div style={styles.wrapper}>
      <div style={styles.header}>
        <h3 style={styles.title}>Carte des courses</h3>
        {!loading && !error && (
          <span style={styles.legend}>
            <span style={styles.dotBlue} /> Avec membres TCN
            <span style={styles.dotGray} /> Autres courses importées
          </span>
        )}
      </div>

      {loading && <p style={styles.msg}>Géolocalisation des courses…</p>}
      {error   && <p style={styles.err}>{error}</p>}
      {!loading && !error && events.length === 0 && (
        <p style={styles.msg}>Aucune course géolocalisée pour l'instant.</p>
      )}

      {/* Always render the div; Leaflet mounts into it */}
      <div
        ref={mapRef}
        style={{
          ...styles.map,
          display: (!loading && !error && events.length > 0) ? "block" : "none",
        }}
      />

      {/* Leaflet CSS loaded inline */}
      <link
        rel="stylesheet"
        href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
      />
    </div>
  );
}

const styles = {
  wrapper: { background: "#fff", borderRadius: 10, padding: "16px 20px", boxShadow: "0 1px 4px rgba(0,0,0,0.08)", marginBottom: 16 },
  header:  { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 },
  title:   { fontSize: 14, fontWeight: 700, color: "#4a5568", textTransform: "uppercase", letterSpacing: "0.05em", margin: 0 },
  legend:  { display: "flex", alignItems: "center", gap: 12, fontSize: 12, color: "#718096" },
  dotBlue: { display: "inline-block", width: 10, height: 10, borderRadius: "50%", background: "#3b82f6", marginRight: 4 },
  dotGray: { display: "inline-block", width: 10, height: 10, borderRadius: "50%", background: "#94a3b8", marginRight: 4, marginLeft: 8 },
  map:     { height: 380, borderRadius: 8, overflow: "hidden" },
  msg:     { color: "#718096", textAlign: "center", padding: 40 },
  err:     { color: "#e53e3e", textAlign: "center", padding: 20 },
};
