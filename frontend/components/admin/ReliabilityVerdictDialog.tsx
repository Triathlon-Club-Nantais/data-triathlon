"use client";
import { useRef, useState } from "react";
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
/**
 * Un seul verbe par geste, porté identiquement par le bouton de ligne, le CTA
 * de la modale et le toast de confirmation (revue UI/UX #119, constat 4) :
 * « OK » était du jargon là où le domaine dit « fiable » partout (l'indice
 * s'appelle « indice de fiabilité »), et « Confirmer » ne nommait pas le
 * verdict posé, contrairement au reste du back-office (« Filtrer »,
 * « Épreuve corrigée. »).
 */
const TEXTES: Record<
  Verdict,
  { titre: string; corps: string; valeur: boolean | null; cta: string; toast: string }
> = {
  fiable: {
    titre: "Marquer cette épreuve comme fiable",
    corps:
      "Elle sortira de la file de revalidation. L'indice calculé, lui, est conservé : il reparaîtra si vous revenez à l'avis de la machine.",
    valeur: true,
    cta: "Marquer fiable",
    toast: "Épreuve marquée fiable.",
  },
  douteuse: {
    titre: "Marquer cette épreuve comme douteuse",
    corps:
      "Elle restera dans la file de revalidation, même si la machine ne relève plus rien après un re-scrape.",
    valeur: false,
    cta: "Marquer douteuse",
    toast: "Épreuve marquée douteuse.",
  },
  calcule: {
    titre: "Revenir à l'avis calculé",
    corps:
      "Votre décision est retirée et l'épreuve reprend le dernier verdict de la machine en date — pas celui qui valait au moment de votre décision.",
    valeur: null,
    cta: "Revenir à l'avis calculé",
    toast: "Avis calculé rétabli.",
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
            cta={textes.cta}
            toast={textes.toast}
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
  cta,
  toast: toastMessage,
  onOpenChange,
}: {
  courseId: number;
  valeur: boolean | null;
  cta: string;
  toast: string;
  onOpenChange: (ouvert: boolean) => void;
}) {
  const [motif, setMotif] = useState("");
  const decision = useSetCourseReliability();
  // Garde **synchrone**, pas `decision.isPending` : cet état ne se met à jour
  // qu'au re-render que déclenche TanStack Query après le démarrage de
  // `mutateAsync`, un tick après le clic. Deux clics enchaînés dans le même
  // tick (double-clic réel) le liraient donc tous les deux à `false` et
  // passeraient au travers — un `useRef` change de valeur immédiatement,
  // sans attendre de re-render, et ferme la fenêtre.
  const enVol = useRef(false);

  async function confirmer() {
    if (enVol.current) return;
    enVol.current = true;
    try {
      await decision.mutateAsync({
        courseId,
        verdict: valeur,
        notes: motif.trim() || undefined,
      });
      toast.success(toastMessage);
      onOpenChange(false);
    } catch (erreur) {
      toast.error(erreur instanceof Error ? erreur.message : "Décision refusée.");
    } finally {
      enVol.current = false;
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
          {decision.isPending ? "Enregistrement…" : cta}
        </Button>
      </DialogFooter>
    </>
  );
}
