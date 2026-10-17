"use client";
import Link from "next/link";
import type { ReactNode } from "react";
import { Card } from "@/components/tcn";
import { nomComplet, useSelectedAthlete } from "@/components/layout/AthletePicker";
import { NAV, ROLE, estVisible } from "@/components/layout/nav.config";
import { useSession } from "@/lib/queries/auth";
import { libelleCompteur, totalATraiter, useNavBadges } from "@/lib/queries/nav-badges";
import { formatDate } from "@/lib/utils/date";
import { motCompte } from "@/lib/utils/format";

function Tuile({ href, titre, ligne, badge }: { href: string; titre: string; ligne?: ReactNode; badge?: ReactNode }) {
  return (
    <Link href={href} className="tcn-tuile-espace block rounded-[var(--tcn-radius-xl)]">
      <Card style={{ height: "100%" }}>
        <div className="flex items-center justify-between gap-2">
          <span style={{ fontFamily: "var(--tcn-font-display)", fontSize: 22, color: "var(--tcn-ink)" }}>{titre}</span>
          <span aria-hidden="true" className="text-accent-ink" style={{ fontWeight: 800 }}>→</span>
        </div>
        {(ligne || badge) && (
          <div className="mt-1 flex items-center gap-2" style={{ fontSize: 14, color: "var(--tcn-text-muted)" }}>
            {badge}
            {ligne}
          </div>
        )}
      </Card>
    </Link>
  );
}

/** Les portes de l'accueil (#1621) ; les espaces réservés n'apparaissent qu'une fois la session lue. */
export function TuilesEspaces({ derniereEpreuve, podiumsSaison }: { derniereEpreuve: { nom: string; date: string | null } | null; podiumsSaison: number }) {
  const { data: session } = useSession();
  const athlete = useSelectedAthlete();
  const { counts } = useNavBadges(Boolean(session?.can_administer));
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
        href="/resultats"
        titre="Résultats"
        ligne={derniereEpreuve ? `${derniereEpreuve.nom}${derniereEpreuve.date ? ` · ${formatDate(derniereEpreuve.date)}` : ""}` : "Toutes les épreuves du club"}
      />
      <Tuile href="/club" titre="Club" ligne={`${motCompte(podiumsSaison, "podium")} cette saison`} />
      <Tuile href="/mon-espace" titre="Mon espace" ligne={athlete ? nomComplet(athlete) : "Choisissez votre nom"} />
      {session?.can_supervise && <Tuile href="/encadrement" titre="Encadrement" ligne="Jeunes, appel, bénévolat" />}
      {session?.can_administer && (
        <Tuile
          href="/admin"
          titre="Back-office"
          badge={aTraiter ? <span aria-label={libelleCompteur("backoffice", aTraiter)} className="rounded-full px-2 text-xs font-extrabold text-white" style={{ background: "var(--tcn-orange-deeper)" }}>{aTraiter}</span> : undefined}
          ligne="À traiter, données, paramétrage"
        />
      )}
    </nav>
  );
}
