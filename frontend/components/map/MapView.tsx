"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { MapContainer, TileLayer, CircleMarker, Popup, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { Alert, Button, SegmentedControl } from "@/components/tcn";
import { apiClient } from "@/lib/api/client";
import { messageDeRefus } from "@/lib/api/refus";
import { eventTypeLabel } from "@/lib/constants";
import { CLUB_NAME_SHORT } from "@/lib/club";
import { formatMonth } from "@/lib/utils/date";
import { upcomingEvents, sortByDistance } from "@/lib/utils/map-filters";
import type { GeoEvent } from "@/lib/types";
import { COULEURS_CARTE, LIBELLE_CHARGEMENT } from "./carte";
import { ListeEpreuves } from "./ListeEpreuves";

// Corrige les chemins d'icônes cassés par les bundlers (icônes via CDN).
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

/**
 * Rayon (px) d'un cercle de la carte, proportionnel au nombre de
 * participants. Le plancher est le rayon d'une cible tactile de 24 px de
 * diamètre (WCAG 2.2 2.5.8) — sous ce seuil, un cercle représentant une
 * épreuve à faible effectif devenait un point cliquable de 20 px (#479).
 */
export function rayonCercle(count: number, maxCount: number): number {
  return Math.max(12, Math.min(40, 10 + (count / maxCount) * 30));
}

function FitBounds({ events }: { events: GeoEvent[] }) {
  const map = useMap();
  useEffect(() => {
    if (events.length === 0) return;
    const bounds = L.latLngBounds(events.map((e) => [e.lat, e.lon]));
    map.fitBounds(bounds, { padding: [30, 30], maxZoom: 9 });
  }, [events, map]);
  return null;
}

/**
 * Un doigt posé pour faire défiler la page glissait la carte à la place
 * (piège de défilement, WCAG 2.2 2.5.7) : `dragging` suit `deverrouillee` au
 * lieu de rester à sa valeur par défaut. Le pincement (`touchZoom`) exige déjà
 * deux doigts, donc n'entre jamais en conflit avec un défilement à un doigt —
 * seul le glisser-déposer à un doigt est le vrai piège.
 */
function VerrouGlisse({ verrouillee }: { verrouillee: boolean }) {
  const map = useMap();
  useEffect(() => {
    if (verrouillee) map.dragging.disable();
    else map.dragging.enable();
  }, [verrouillee, map]);
  return null;
}

function pointeurGrossier(): boolean {
  return typeof window.matchMedia === "function" && window.matchMedia("(pointer: coarse)").matches;
}

export function MapView({ scope }: { scope?: string }) {
  const [events, setEvents] = useState<GeoEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [erreur, setErreur] = useState<Error | null>(null);
  // Le `useEffect` ne dépendait que de `scope` : rien, sur un écran en erreur, ne
  // permettait de redemander. Ce compteur est le seul état que « Réessayer »
  // change (#299).
  const [essai, setEssai] = useState(0);
  // `MapView` est chargé en `next/dynamic({ ssr: false })` (app/(public_restricted)/carte/page.tsx) :
  // toujours monté côté client, `window` y existe donc dès ce premier rendu.
  const [verrouillee, setVerrouillee] = useState(pointeurGrossier);
  // Période et tri (US12, #466) : deux filtres indépendants, combinables.
  const [periode, setPeriode] = useState<"toutes" | "a-venir">("toutes");
  const [tri, setTri] = useState<"defaut" | "distance">("defaut");

  useEffect(() => {
    let abandonne = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    setErreur(null);
    apiClient
      .getEventsGeo({ scope })
      .then((recus) => {
        if (!abandonne) setEvents(recus);
      })
      .catch((cause: Error) => {
        if (!abandonne) setErreur(cause);
      })
      .finally(() => {
        if (!abandonne) setLoading(false);
      });
    return () => {
      abandonne = true;
    };
  }, [scope, essai]);

  const reessayer = useCallback(() => setEssai((n) => n + 1), []);

  const eventsAffiches = useMemo(() => {
    const filtres = periode === "a-venir" ? upcomingEvents(events, new Date()) : events;
    return tri === "distance" ? sortByDistance(filtres) : filtres;
  }, [events, periode, tri]);

  if (loading) return <p className="py-10 text-center text-[var(--tcn-text-body)]">{LIBELLE_CHARGEMENT}</p>;

  if (erreur) {
    // Le message disait « Impossible de charger la carte » — ni la cause, ni quoi
    // faire. `messageDeRefus` distingue déjà la session expirée du refus et de la
    // panne, sur les quatre autres écrans qui l'utilisent.
    const { title, description } = messageDeRefus(erreur, {
      sujet: "lieux des épreuves",
      action: "consulter la carte",
    });
    return (
      <Alert
        status="error"
        title={title}
        action={
          <Button variant="secondary" size="sm" onClick={reessayer}>
            Réessayer
          </Button>
        }
      >
        {description}
      </Alert>
    );
  }

  if (events.length === 0) {
    // L'état vide ne proposait rien, alors que /ajouter est le chemin qui
    // remplit la carte.
    return (
      <Alert status="warning" title="Aucune épreuve géolocalisée">
        Les épreuves apparaissent ici dès qu&apos;une participation est importée.{" "}
        <Link href="/ajouter" className="font-semibold underline">
          Ajouter une épreuve
        </Link>
        .
      </Alert>
    );
  }

  const maxCount = Math.max(...events.map((e) => e.count), 1);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3" role="group" aria-label="Filtrer les épreuves de la carte">
        <SegmentedControl
          options={[
            { value: "toutes", label: "Toutes" },
            { value: "a-venir", label: "À venir" },
          ]}
          value={periode}
          onChange={(v) => setPeriode(v as "toutes" | "a-venir")}
        />
        <SegmentedControl
          options={[
            { value: "defaut", label: "Tri par défaut" },
            { value: "distance", label: `Plus proches de ${CLUB_NAME_SHORT}` },
          ]}
          value={tri}
          onChange={(v) => setTri(v as "defaut" | "distance")}
        />
      </div>
      {eventsAffiches.length === 0 && (
        <Alert
          status="warning"
          title={periode === "a-venir" ? "Aucune épreuve à venir" : "Aucune épreuve pour ce filtre"}
        >
          Aucune épreuve géolocalisée ne correspond à ce filtre pour le moment.
        </Alert>
      )}
      <div className="relative">
        {verrouillee && (
          // Avant `MapContainer` dans le DOM (et non seulement au-dessus par
          // z-index) : tant que la carte est verrouillée, ses contrôles de zoom
          // internes à Leaflet ne doivent pas être le premier arrêt clavier —
          // leur anneau de focus se peindrait sous ce voile opaque, invisible.
          <button
            type="button"
            onClick={() => setVerrouillee(false)}
            className="absolute inset-0 z-[1000] flex items-center justify-center rounded-md text-center focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--tcn-orange)]"
            // `--tcn-overlay` (45 %) est calibré pour un scrim de modale, sous un
            // panneau opaque — ici le texte lui est posé dessus, directement sur
            // des tuiles parfois claires : il faut son propre contraste garanti,
            // d'où `--tcn-ink` à 85 % plutôt que le token de scrim.
            style={{ background: "rgba(28, 30, 34, 0.85)" }}
          >
            <span className="rounded-full border border-white/70 px-4 py-2 font-semibold text-white">
              Toucher pour activer la carte
            </span>
          </button>
        )}
        <MapContainer center={[47.2, -1.5]} zoom={7} scrollWheelZoom={false} className="h-[320px] w-full rounded-md sm:h-[480px]">
          <TileLayer
            attribution='© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            maxZoom={13}
          />
          {eventsAffiches.map((ev, i) => {
            const radius = rayonCercle(ev.count, maxCount);
            const teinte = ev.tcn_count > 0 ? COULEURS_CARTE.avecTcn : COULEURS_CARTE.sansTcn;
            return (
              <CircleMarker
                key={`${ev.event_name}-${i}`}
                center={[ev.lat, ev.lon]}
                radius={radius}
                pathOptions={{
                  fillColor: teinte.remplissage,
                  color: teinte.trait,
                  weight: teinte.epaisseur,
                  dashArray: teinte.pointilles,
                  fillOpacity: 0.55,
                }}
              >
                <Popup>
                  <div className="min-w-[180px]">
                    <b>
                      <Link
                        href={`/courses/${ev.course_id}`}
                        className="underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--tcn-orange)]"
                      >
                        {ev.event_name}
                      </Link>
                    </b>
                    {ev.event_type && <div className="text-[var(--tcn-text-body)]">{eventTypeLabel(ev.event_type)}</div>}
                    {ev.event_date && <div className="text-xs">{formatMonth(ev.event_date.slice(0, 7))}</div>}
                    <div>
                      {ev.count} participant{ev.count > 1 ? "s" : ""}
                    </div>
                    {ev.tcn_count > 0 && (
                      <div className="font-semibold text-[var(--tcn-danger-text)]">
                        {ev.tcn_count} membre{ev.tcn_count > 1 ? "s" : ""} {CLUB_NAME_SHORT}
                      </div>
                    )}
                  </div>
                </Popup>
              </CircleMarker>
            );
          })}
          <FitBounds events={eventsAffiches} />
          <VerrouGlisse verrouillee={verrouillee} />
        </MapContainer>
      </div>
      <ListeEpreuves events={eventsAffiches} />
    </div>
  );
}
