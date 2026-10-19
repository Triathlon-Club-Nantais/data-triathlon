"use client";
import { ArrowRight } from "lucide-react";
import Link from "next/link";
import type { CSSProperties, ReactNode } from "react";
import { Card } from "@/components/tcn";
import { nomComplet, useSelectedAthlete } from "@/components/layout/AthletePicker";
import { NAV, ROLE, estVisible } from "@/components/layout/nav.config";
import { useHydratedSession } from "@/lib/queries/auth";
import { useEpreuvesSaison } from "@/lib/queries/ma-saison";
import { libelleCompteur, totalATraiter, useNavBadges } from "@/lib/queries/nav-badges";
import { formatDate } from "@/lib/utils/date";
import { motCompte } from "@/lib/utils/format";
import { currentSeason } from "@/lib/utils/season";

function Tuile({ index, href, titre, ligne, badge }: { index: number; href: string; titre: string; ligne?: ReactNode; badge?: ReactNode }) {
  return (
    <div className="tcn-tuile-entree" style={{ "--i": index } as CSSProperties}>
    <Link href={href} className="tcn-tuile-espace block h-full rounded-[var(--tcn-radius-3xl)]">
      <Card style={{ height: "100%", background: "var(--tuile-fond, var(--tcn-surface))" }}>
        <div className="flex items-center justify-between gap-2">
          <h2 style={{ fontFamily: "var(--tcn-font-display)", fontSize: 22, fontWeight: "inherit", margin: 0, color: "var(--tcn-ink)" }}>{titre}</h2>
          <span aria-hidden="true" className="tcn-tuile-fleche"><ArrowRight size={18} /></span>
        </div>
        {(ligne || badge) && (
          <div className="mt-1 flex items-center gap-2" style={{ fontSize: 14, color: "var(--tcn-text-muted)" }}>
            {badge}
            {ligne}
          </div>
        )}
      </Card>
    </Link>
    </div>
  );
}

/** Les portes de l'accueil (#1621) ; les espaces réservés n'apparaissent qu'une fois la session lue. */
export function TuilesEspaces({ derniereEpreuve, podiumsSaison, query, seasons }: { derniereEpreuve: { nom: string; date: string | null } | null; podiumsSaison: number; query: string; seasons: number[] }) {
  const { data: session } = useHydratedSession();
  const athlete = useSelectedAthlete();
  const epreuves = useEpreuvesSaison(athlete?.id, seasons);
  const { counts } = useNavBadges(Boolean(session?.can_administer));
  const periode = seasons.length === 1 && seasons[0] === currentSeason() ? "cette saison" : "sur la sélection";
  const pouvoirs = new Set(session?.permissions ?? []);
  const aTraiter = session?.can_administer
    ? totalATraiter(
        NAV.flatMap((s) => s.items)
          .filter((i) => estVisible(i, pouvoirs, ROLE.CONNECTED))
          .map((i) => (i.badge ? { ...i, count: counts[i.badge] } : i)),
      )
    : undefined;

  return (
    <nav aria-label="Espaces" className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <Tuile
        index={0}
        href={`/resultats${query}`}
        titre="Résultats"
        ligne={derniereEpreuve ? `${derniereEpreuve.nom}${derniereEpreuve.date ? ` · ${formatDate(derniereEpreuve.date)}` : ""}` : "Toutes les épreuves du club"}
      />
      <Tuile index={1} href={`/club${query}`} titre="Club" ligne={`${motCompte(podiumsSaison, "podium")} ${periode}`} />
      <Tuile index={2} href={`/mon-espace${query}`} titre="Mon espace" ligne={athlete ? (epreuves === undefined ? nomComplet(athlete) : `${nomComplet(athlete)} · ${motCompte(epreuves, "épreuve")} ${periode}`) : "Choisissez votre nom"} />
      {session?.can_supervise && <Tuile index={3} href="/encadrement" titre="Encadrement" ligne="Jeunes, appel, bénévolat" />}
      {session?.can_administer && (
        <Tuile
          index={4}
          href="/admin"
          titre="Back-office"
          badge={aTraiter ? <span className="rounded-full px-2 text-xs font-extrabold text-white" style={{ background: "var(--tcn-orange-deeper)" }}><span aria-hidden="true">{aTraiter}</span><span className="sr-only">{libelleCompteur("backoffice", aTraiter)}</span></span> : undefined}
          ligne="À traiter, données, paramétrage"
        />
      )}
    </nav>
  );
}
