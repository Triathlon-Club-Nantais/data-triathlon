"use client";
import Link from "next/link";
import type { ReactNode } from "react";
import { Card } from "@/components/tcn";
import { nomComplet, useSelectedAthlete } from "@/components/layout/AthletePicker";
import { NAV, ROLE, estVisible } from "@/components/layout/nav.config";
import { useHydratedSession } from "@/lib/queries/auth";
import { useEpreuvesSaison } from "@/lib/queries/ma-saison";
import { libelleCompteur, totalATraiter, useNavBadges } from "@/lib/queries/nav-badges";
import { formatDate } from "@/lib/utils/date";
import { motCompte } from "@/lib/utils/format";

function Tuile({ href, titre, ligne, badge }: { href: string; titre: string; ligne?: ReactNode; badge?: ReactNode }) {
  return (
    <Link href={href} className="tcn-tuile-espace block rounded-[var(--tcn-radius-3xl)]">
      <Card style={{ height: "100%", background: "var(--tuile-fond, var(--tcn-surface))" }}>
        <div className="flex items-center justify-between gap-2">
          <h2 style={{ fontFamily: "var(--tcn-font-display)", fontSize: 22, fontWeight: "inherit", margin: 0, color: "var(--tcn-ink)" }}>{titre}</h2>
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
  const { data: session } = useHydratedSession();
  const athlete = useSelectedAthlete();
  const epreuves = useEpreuvesSaison(athlete?.id);
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
      <Tuile href="/mon-espace" titre="Mon espace" ligne={athlete ? (epreuves === undefined ? nomComplet(athlete) : `${nomComplet(athlete)} · ${motCompte(epreuves, "épreuve")} cette saison`) : "Choisissez votre nom"} />
      {session?.can_supervise && <Tuile href="/encadrement" titre="Encadrement" ligne="Jeunes, appel, bénévolat" />}
      {session?.can_administer && (
        <Tuile
          href="/admin"
          titre="Back-office"
          badge={aTraiter ? <span className="rounded-full px-2 text-xs font-extrabold text-white" style={{ background: "var(--tcn-orange-deeper)" }}><span aria-hidden="true">{aTraiter}</span><span className="sr-only">{libelleCompteur("backoffice", aTraiter)}</span></span> : undefined}
          ligne="À traiter, données, paramétrage"
        />
      )}
    </nav>
  );
}
