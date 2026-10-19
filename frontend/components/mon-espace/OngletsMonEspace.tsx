"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { EventsTable } from "@/components/athletes/EventsTable";
import { AthleteChallenges } from "@/components/challenges/AthleteChallenges";
import { SeasonGoals } from "@/components/dashboard/SeasonGoals";
import { Card } from "@/components/tcn";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { messageDeRefus } from "@/lib/api/refus";
import { useMyVolunteerActions } from "@/lib/queries/auth";
import type { AthleteChallenge, Participation } from "@/lib/types";
import { formatDate } from "@/lib/utils/date";
import { OngletRecords } from "./OngletRecords";

const ONGLET_PARAM = "onglet";

const REFUS = {
  sujet: "vos actions de bénévolat",
  action: "consulter vos actions de bénévolat",
};

function MesActionsBenevolat() {
  const actions = useMyVolunteerActions(true);
  const lien = (
    <Link href="/benevolat" className="font-semibold text-accent-ink underline underline-offset-2">
      Déclarer une action
    </Link>
  );

  return (
    <Card>
      <h2 style={{ fontFamily: "var(--tcn-font-display)", fontSize: 22, fontWeight: 400, color: "var(--tcn-ink)", margin: 0 }}>
        Actions de bénévolat validées
      </h2>
      {actions.isPending ? (
        <Skeleton className="mt-4 h-16 w-full" />
      ) : actions.isError ? (
        <EmptyState bare {...messageDeRefus(actions.error, REFUS)} />
      ) : actions.data.length === 0 ? (
        <EmptyState bare title="Aucune action de bénévolat validée" description={<>{lien} pour qu&apos;elle apparaisse ici une fois acceptée.</>} />
      ) : (
        <>
          <ul style={{ listStyle: "none", padding: 0, margin: "12px 0 0" }}>
            {actions.data.map((action) => (
              <li key={action.id} style={{ marginTop: 10 }}>
                <strong>{action.title ?? "Action sans titre"}</strong>
                <span style={{ color: "var(--tcn-text-faint)" }}> ({formatDate(action.created_at)}, saison {action.season})</span>
              </li>
            ))}
          </ul>
          <p style={{ marginTop: 16 }}>{lien}</p>
        </>
      )}
    </Card>
  );
}

/** Carte à onglets de Mon espace (#1696) : l'onglet vit dans `?onglet=`, écrit par l'historique natif comme `EventsTable`. */
export function OngletsMonEspace({
  athleteId,
  athleteName,
  participations,
  challenges,
  federalOnly,
}: {
  federalOnly: boolean;
  athleteId: number;
  athleteName: string;
  participations: Participation[];
  challenges: AthleteChallenge[];
}) {
  const pathname = usePathname();
  const sp = useSearchParams();
  const onglets = [
    { value: "records", label: "Records" },
    { value: "epreuves", label: "Épreuves" },
    { value: "benevolat", label: "Bénévolat" },
    { value: "objectifs", label: "Objectifs" },
  ];
  const courant = onglets.find((o) => o.value === sp.get(ONGLET_PARAM))?.value ?? onglets[0].value;

  function choisir(valeur: unknown) {
    const params = new URLSearchParams(sp.toString());
    params.set(ONGLET_PARAM, String(valeur));
    window.history.pushState(null, "", `${pathname}?${params.toString()}`);
  }

  return (
    <Tabs value={courant} onValueChange={choisir}>
      <TabsList variant="line" aria-label="Mon espace" activateOnFocus>
        {onglets.map((o) => (
          <TabsTrigger key={o.value} value={o.value}>
            {o.label}
          </TabsTrigger>
        ))}
      </TabsList>
      <TabsContent value="records">
        <OngletRecords athleteId={athleteId} federalOnly={federalOnly} selection={participations} />
      </TabsContent>
      <TabsContent value="epreuves" className="space-y-6">
        <EventsTable participations={participations} athleteId={athleteId} athleteName={athleteName} />
        <AthleteChallenges challenges={challenges} />
      </TabsContent>
      <TabsContent value="benevolat">
        <MesActionsBenevolat />
      </TabsContent>
      <TabsContent value="objectifs">
        <SeasonGoals />
      </TabsContent>
    </Tabs>
  );
}
