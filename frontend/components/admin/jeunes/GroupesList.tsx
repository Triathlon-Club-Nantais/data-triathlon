"use client";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { GroupeDetail } from "@/components/admin/jeunes/GroupeDetail";
import { useCreateTrainingGroup, useTrainingGroups } from "@/lib/queries/admin";
import { useSession } from "@/lib/queries/auth";
import { messageDeRefus } from "@/lib/api/refus";

const REFUS = { sujet: "groupes", action: "consulter les groupes" };

/** Les groupes d'entraînement (#1291) : cartes seules, l'écran se tient au téléphone. */
export function GroupesList() {
  const { data, isPending, error } = useTrainingGroups();
  const session = useSession();
  const creer = useCreateTrainingGroup();
  const [nom, setNom] = useState("");
  const [ouvert, setOuvert] = useState<number | null>(null);

  const peutEcrire = session.data?.permissions.includes("jeunes:write") ?? false;

  async function soumettre(evenement: React.SyntheticEvent) {
    evenement.preventDefault();
    if (!nom.trim()) return;
    try {
      await creer.mutateAsync(nom.trim());
      setNom("");
      toast.success("Groupe créé.");
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  return (
    <div className="space-y-4">
      {peutEcrire && (
        <form onSubmit={soumettre} className="flex flex-wrap items-end gap-2">
          <div className="min-w-0 flex-1 space-y-1.5 sm:max-w-xs">
            <Label htmlFor="groupe-nom">Nom du groupe</Label>
            <Input
              id="groupe-nom"
              required
              placeholder="Benjamins mercredi"
              value={nom}
              onChange={(e) => setNom(e.target.value)}
            />
          </div>
          <Button type="submit" disabled={creer.isPending}>
            Créer le groupe
          </Button>
        </form>
      )}

      {isPending ? (
        <Skeleton className="h-40 w-full" />
      ) : error ? (
        <EmptyState {...messageDeRefus(error, REFUS)} />
      ) : !data || data.length === 0 ? (
        <EmptyState
          title="Aucun groupe"
          description="Un groupe rassemble les jeunes d'un même créneau : une séance qui le vise les inscrit d'office."
        />
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {data.map((groupe) => (
            <Card
              key={groupe.id}
              role="button"
              tabIndex={0}
              onClick={() => setOuvert(groupe.id)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  setOuvert(groupe.id);
                }
              }}
              className="cursor-pointer p-4 transition-colors hover:bg-[var(--tcn-orange-08)]"
            >
              <div className="font-medium">{groupe.name}</div>
              <div className="text-[var(--tcn-text-faint)] text-sm">
                {groupe.member_count} membre{groupe.member_count > 1 ? "s" : ""}
              </div>
            </Card>
          ))}
        </div>
      )}

      {ouvert !== null && (
        <GroupeDetail
          groupId={ouvert}
          peutEcrire={peutEcrire}
          onOpenChange={(o) => !o && setOuvert(null)}
        />
      )}
    </div>
  );
}
