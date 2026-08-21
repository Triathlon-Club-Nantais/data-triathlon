"use client";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { describeQualityIssues } from "@/lib/quality";
import { useSetCourseReliability } from "@/lib/queries/admin";
import type { CourseBrief } from "@/lib/types";

/** Les trois gestes que porte `PATCH …/reliability`, nommés côté écran. */
export type Verdict = "fiable" | "douteuse" | "calcule";

/**
 * Un seul dialogue pour les trois gestes de verdict (#119).
 *
 * Trois modales quasi identiques auraient divergé au premier ajustement de
 * microcopie, et le champ « motif » — le seul contenu réel de l'écran — y aurait
 * été recopié trois fois. Ce qui change entre les gestes tient dans la table
 * `TEXTES` ci-dessous.
 *
 * Le motif est **facultatif** : un verdict sans commentaire reste un verdict, et
 * rendre la saisie obligatoire ferait écrire « ok » trois cents fois.
 */
const TEXTES: Record<Verdict, { titre: string; corps: string; valeur: boolean | null }> = {
  fiable: {
    titre: "Marquer cette épreuve comme fiable",
    corps:
      "Elle sortira de la file de revalidation. L'indice calculé, lui, est conservé : il reparaîtra si vous revenez à l'avis de la machine.",
    valeur: true,
  },
  douteuse: {
    titre: "Marquer cette épreuve comme douteuse",
    corps:
      "Elle restera dans la file de revalidation, même si la machine ne relève plus rien après un re-scrape.",
    valeur: false,
  },
  calcule: {
    titre: "Revenir à l'avis calculé",
    corps:
      "Votre décision est retirée et l'épreuve reprend le **dernier** verdict de la machine — pas celui qui valait au moment de votre décision.",
    valeur: null,
  },
};

export function ReliabilityVerdictDialog({
  course,
  verdict,
  onOpenChange,
}: {
  course: CourseBrief;
  /** `null` = fermé. */
  verdict: Verdict | null;
  onOpenChange: (ouvert: boolean) => void;
}) {
  const textes = verdict ? TEXTES[verdict] : null;
  const anomalies = describeQualityIssues(course.quality_issues);

  return (
    <Dialog open={verdict !== null} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{textes?.titre}</DialogTitle>
          <DialogDescription>
            {course.name} — {textes?.corps}
          </DialogDescription>
        </DialogHeader>

        {anomalies.length > 0 && (
          <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
            {anomalies.map((phrase) => (
              <li key={phrase}>{phrase}</li>
            ))}
          </ul>
        )}

        {/* Clé sur l'épreuve et le geste : rouvrir sur une autre épreuve, ou sur
            un autre geste pour la même, remonte le formulaire à neuf plutôt que
            d'hériter du motif précédent — ce serait consigner au journal une
            justification écrite pour un autre cas. */}
        {textes && (
          <Corps
            key={`${course.id}-${verdict}`}
            courseId={course.id}
            valeur={textes.valeur}
            onOpenChange={onOpenChange}
          />
        )}
      </DialogContent>
    </Dialog>
  );
}

function Corps({
  courseId,
  valeur,
  onOpenChange,
}: {
  courseId: number;
  valeur: boolean | null;
  onOpenChange: (ouvert: boolean) => void;
}) {
  const [motif, setMotif] = useState("");
  const decision = useSetCourseReliability();

  async function confirmer() {
    try {
      await decision.mutateAsync({
        courseId,
        verdict: valeur,
        notes: motif.trim() || undefined,
      });
      toast.success("Décision enregistrée.");
      onOpenChange(false);
    } catch (erreur) {
      toast.error(erreur instanceof Error ? erreur.message : "Décision refusée.");
    }
  }

  return (
    <>
      <div className="space-y-2">
        <Label htmlFor="motif-verdict">Motif (facultatif)</Label>
        <Textarea
          id="motif-verdict"
          value={motif}
          maxLength={500}
          onChange={(e) => setMotif(e.target.value)}
          placeholder="Ce qui a été vérifié, et comment."
        />
      </div>

      <DialogFooter>
        <Button variant="outline" onClick={() => onOpenChange(false)}>
          Annuler
        </Button>
        <Button onClick={confirmer} disabled={decision.isPending}>
          {decision.isPending ? "Enregistrement…" : "Confirmer"}
        </Button>
      </DialogFooter>
    </>
  );
}
