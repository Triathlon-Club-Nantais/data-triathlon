import Link from "next/link";

/**
 * Rappel épinglé de la position de l'athlète retenu (#504) — affiché quand sa
 * ligne/fiche est hors de l'aperçu visible du roster (`/club`,
 * `/club/athletes`). Toujours monté, hauteur réservée par le conteneur : le
 * signifiant n'existe qu'après hydratation (`useSelectedAthlete`, jamais dans
 * le HTML initial, `frontend/AGENTS.md`), et sans réservation son apparition
 * déplacerait la section sous lui.
 */
export function RappelPosition({
  visible,
  epreuves,
  rang,
  hrefAncre,
}: {
  visible: boolean;
  epreuves: number;
  rang: number;
  hrefAncre: string;
}) {
  return (
    <div className="min-h-11">
      {visible && (
        <Link
          href={hrefAncre}
          className="inline-flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold"
          style={{
            background: "var(--tcn-orange-08)",
            border: "1px solid rgba(233,83,14,.25)",
            color: "var(--tcn-orange-deeper)",
          }}
        >
          Vous : {epreuves} épreuve{epreuves > 1 ? "s" : ""} — {rang}ᵉ du club
        </Link>
      )}
    </div>
  );
}
