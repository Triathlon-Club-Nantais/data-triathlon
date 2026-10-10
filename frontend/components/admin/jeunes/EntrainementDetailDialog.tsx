"use client";
import Link from "next/link";
import { toast } from "sonner";
import { Button, buttonVariants } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useDangerConfirm } from "@/components/admin/DangerConfirm";
import { EntrainementForm } from "@/components/admin/jeunes/EntrainementForm";
import { ParticipantsList } from "@/components/admin/jeunes/ParticipantsList";
import {
  useDeleteTrainingSession,
  useTrainingGroups,
  useUpdateTrainingSession,
} from "@/lib/queries/admin";
import { formatDate } from "@/lib/utils/date";
import type { TrainingSession } from "@/lib/types";

/**
 * Le détail d'une séance : sa correction et sa liste de participants
 * (#868). Même patron que `GroupDetailDialog` — la prop fait foi tant que le
 * détail n'est pas arrivé, jamais après.
 */
export function EntrainementDetailDialog({
  entrainement,
  peutEcrire,
  open,
  onOpenChange,
}: {
  entrainement: TrainingSession;
  peutEcrire: boolean;
  open: boolean;
  onOpenChange: (ouvert: boolean) => void;
}) {
  const modifier = useUpdateTrainingSession();
  const supprimer = useDeleteTrainingSession();
  const confirmer = useDangerConfirm();
  const groupes = useTrainingGroups();

  async function enregistrer(champs: {
    date: string;
    start_time: string | null;
    location: string | null;
    session_type: string | null;
    group_ids?: number[];
  }) {
    try {
      await modifier.mutateAsync({ id: entrainement.id, champs });
      toast.success("Séance modifiée.");
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  async function detruire() {
    const accord = await confirmer({
      titre: `Supprimer la séance du ${formatDate(entrainement.date)} ?`,
      description:
        "La séance disparaît du calendrier avec ses inscriptions, ses présences et sa note. Ce geste est définitif.",
      libelleAction: "Supprimer la séance",
    });
    if (!accord) return;
    try {
      await supprimer.mutateAsync(entrainement.id);
      toast.success("Séance supprimée.");
      onOpenChange(false);
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85dvh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Séance du {formatDate(entrainement.date)}</DialogTitle>
          <DialogDescription>
            Les jeunes inscrits à cette séance. Une inscription se retire d&apos;un
            clic et se refait tout aussi simplement.
          </DialogDescription>
        </DialogHeader>

        {peutEcrire && (
          <EntrainementForm
            entrainement={entrainement}
            soumettre={enregistrer}
            enCours={modifier.isPending}
            libelleSoumission="Enregistrer"
            groupes={groupes.data}
          />
        )}

        {/* Appel de présence (#869) — route dédiée, mobile-first : ce détail
            reste le point d'entrée le plus court depuis le calendrier. */}
        <Link
          href={`/admin/jeunes/appel/${entrainement.id}`}
          className={buttonVariants({ variant: "outline", size: "sm", className: "w-fit" })}
        >
          Ouvrir l&apos;appel
        </Link>

        <ParticipantsList sessionId={entrainement.id} peutEcrire={peutEcrire} />

        {peutEcrire && (
          <Button
            variant="destructive"
            className="w-fit"
            disabled={supprimer.isPending}
            onClick={detruire}
          >
            Supprimer la séance
          </Button>
        )}
      </DialogContent>
    </Dialog>
  );
}
