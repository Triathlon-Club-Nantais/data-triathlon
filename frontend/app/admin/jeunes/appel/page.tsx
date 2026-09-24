"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/layout/PageHeader";
import { ecran } from "@/components/layout/nav.config";
import { PageShell } from "@/components/layout/PageShell";
import { useCreateEntrainement, useEntrainements } from "@/lib/queries/admin";
import { useSession } from "@/lib/queries/auth";
import { messageDeRefus } from "@/lib/api/refus";
import { localToday } from "@/lib/utils/date";
import type { Entrainement } from "@/lib/types";

const REFUS = { sujet: "les entraînements", action: "ouvrir l'appel" };

function libelleSeance(entrainement: Entrainement): string {
  const parties = [
    entrainement.heure_debut ? entrainement.heure_debut.slice(0, 5) : "Heure non renseignée",
    entrainement.type_seance,
    entrainement.lieu,
  ];
  return parties.filter(Boolean).join(" · ");
}

/**
 * Résout la séance du jour et ouvre son appel (#869, epic #863) — L'appel
 * peut **peupler le calendrier** : une séance datée d'aujourd'hui absente du
 * calendrier se crée ici, en un geste, plutôt que d'obliger l'encadrant à
 * détourner par `/admin/jeunes/calendrier` avant de pouvoir faire l'appel.
 *
 * Plusieurs séances le même jour (natation le matin, course le soir) ne se
 * départagent pas à la place de l'encadrant : il choisit, sans quoi l'appel
 * serait pointé sur la mauvaise séance sans aucun signal.
 */
export default function AdminJeuneAppelDuJourPage() {
  const router = useRouter();
  const { data, isLoading, error } = useEntrainements();
  const session = useSession();
  const creer = useCreateEntrainement();
  const [creationLancee, setCreationLancee] = useState(false);

  const peutEcrire = session.data?.permissions.includes("jeunes:write") ?? false;
  const aujourdhui = localToday();
  const seancesDuJour = (data ?? []).filter((entrainement) => entrainement.date === aujourdhui);
  const seanceUnique = seancesDuJour.length === 1 ? seancesDuJour[0] : null;

  useEffect(() => {
    if (seanceUnique) {
      router.replace(`/admin/jeunes/appel/${seanceUnique.id}`);
    }
  }, [seanceUnique, router]);

  async function creerLaSeanceDuJour() {
    setCreationLancee(true);
    try {
      const entrainement = await creer.mutateAsync({ date: localToday() });
      router.replace(`/admin/jeunes/appel/${entrainement.id}`);
    } catch (e) {
      setCreationLancee(false);
      toast.error((e as Error).message);
    }
  }

  return (
    <PageShell>
      <div className="space-y-10">
        <PageHeader {...ecran("/admin/jeunes/appel")} />
        {isLoading || seanceUnique || creationLancee ? (
          <Skeleton className="h-40 w-full" />
        ) : error ? (
          <EmptyState {...messageDeRefus(error, REFUS)} />
        ) : seancesDuJour.length > 1 ? (
          <div className="space-y-3">
            <p className="text-sm">Plusieurs séances aujourd&apos;hui : choisissez celle de l&apos;appel.</p>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {seancesDuJour.map((entrainement) => (
                <Link key={entrainement.id} href={`/admin/jeunes/appel/${entrainement.id}`}>
                  <Card className="p-4 font-medium transition-colors hover:bg-[var(--tcn-orange-08)]">
                    {libelleSeance(entrainement)}
                  </Card>
                </Link>
              ))}
            </div>
          </div>
        ) : (
          <EmptyState
            title="Aucune séance aujourd'hui"
            description="Le calendrier n'a pas encore de séance datée d'aujourd'hui."
            action={
              peutEcrire ? (
                <Button onClick={creerLaSeanceDuJour} disabled={creer.isPending}>
                  Créer la séance du jour
                </Button>
              ) : undefined
            }
          />
        )}
      </div>
    </PageShell>
  );
}
