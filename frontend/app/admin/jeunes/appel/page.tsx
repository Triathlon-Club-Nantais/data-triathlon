"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/layout/PageHeader";
import { ecran } from "@/components/layout/nav.config";
import { PageShell } from "@/components/layout/PageShell";
import { useCreateEntrainement, useEntrainements } from "@/lib/queries/admin";
import { messageDeRefus } from "@/lib/api/refus";

const REFUS = { sujet: "les entraînements", action: "ouvrir l'appel" };

/** Date locale du jour (`YYYY-MM-DD`) — celle du navigateur de l'encadrant,
 * pas l'UTC du serveur : c'est sa journée sur le terrain qui compte. */
function ajourdhui(): string {
  const maintenant = new Date();
  const annee = maintenant.getFullYear();
  const mois = String(maintenant.getMonth() + 1).padStart(2, "0");
  const jour = String(maintenant.getDate()).padStart(2, "0");
  return `${annee}-${mois}-${jour}`;
}

/**
 * Résout la séance du jour et ouvre son appel (#869, epic #863) — L'appel
 * peut **peupler le calendrier** : une séance datée d'aujourd'hui absente du
 * calendrier se crée ici, en un geste, plutôt que d'obliger l'encadrant à
 * détourner par `/admin/jeunes/calendrier` avant de pouvoir faire l'appel.
 */
export default function AdminJeuneAppelDuJourPage() {
  const router = useRouter();
  const { data, isLoading, error } = useEntrainements();
  const creer = useCreateEntrainement();
  const [creationLancee, setCreationLancee] = useState(false);

  const seanceDuJour = (data ?? []).find((entrainement) => entrainement.date === ajourdhui());

  useEffect(() => {
    if (seanceDuJour) {
      router.replace(`/admin/jeunes/appel/${seanceDuJour.id}`);
    }
  }, [seanceDuJour, router]);

  async function creerLaSeanceDuJour() {
    setCreationLancee(true);
    try {
      const entrainement = await creer.mutateAsync({ date: ajourdhui() });
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
        {isLoading || seanceDuJour || creationLancee ? (
          <Skeleton className="h-40 w-full" />
        ) : error ? (
          <EmptyState {...messageDeRefus(error, REFUS)} />
        ) : (
          <EmptyState
            title="Aucune séance aujourd'hui"
            description="Le calendrier n'a pas encore de séance datée d'aujourd'hui."
            action={
              <Button onClick={creerLaSeanceDuJour} disabled={creer.isPending}>
                Créer la séance du jour
              </Button>
            }
          />
        )}
      </div>
    </PageShell>
  );
}
