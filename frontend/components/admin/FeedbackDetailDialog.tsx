"use client";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { useFeedback, useUpdateFeedbackStatus } from "@/lib/queries/admin";
import { useSession } from "@/lib/queries/auth";
import { formatDate } from "@/lib/utils/date";
import type { Feedback } from "@/lib/types";

const LIBELLE_STATUT: Record<Feedback["status"], string> = {
  nouveau: "Nouveau",
  en_cours: "En cours",
  traite: "Traité",
  ignore: "Ignoré",
};

/**
 * Vue détail d'un signalement (#267, US3) — titre, description, contexte,
 * email conditionnel, et le changement de statut.
 *
 * Le détail fait foi dès qu'il est là, la prop `feedback` (la ligne cliquée
 * dans `FeedbackTable`) ne servant que de repli pendant le chargement — même
 * patron que `GroupDetailDialog` pour un renommage.
 */
export function FeedbackDetailDialog({
  feedback,
  open,
  onOpenChange,
}: {
  feedback: Feedback;
  open: boolean;
  onOpenChange: (ouvert: boolean) => void;
}) {
  const detail = useFeedback(open ? feedback.id : null);
  const session = useSession();
  const changerStatut = useUpdateFeedbackStatus();

  const peutInstruire = session.data?.permissions.includes("feedback:manage") ?? false;
  const affiche = detail.data ?? feedback;

  async function changer(status: Feedback["status"]) {
    try {
      await changerStatut.mutateAsync({ id: feedback.id, status });
      toast.success("Statut mis à jour.");
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{affiche.title}</DialogTitle>
          <DialogDescription>
            Signalé le {formatDate(affiche.created_at)} ·{" "}
            <Badge variant={affiche.type === "bug" ? "destructive" : "secondary"}>
              {affiche.type === "bug" ? "Bug" : "Retour"}
            </Badge>
          </DialogDescription>
        </DialogHeader>

        {/* `affiche` retombe sur la prop — la ligne cliquée dans `FeedbackTable`
            porte déjà un `Feedback` complet, exactement la forme que rend le
            détail. Rien ici n'attend `detail.isLoading` : le contenu est déjà
            là, la requête ne fait que le rafraîchir en tâche de fond. */}
        <div className="space-y-3 text-sm">
          <p className="whitespace-pre-wrap">{affiche.body}</p>
          {affiche.page_url && (
            <p className="text-muted-foreground">
              Page : <span className="break-all">{affiche.page_url}</span>
            </p>
          )}
          {/* `email` est `None` pour un signalement anonyme — data-model.md. */}
          {affiche.email && (
            <p className="text-muted-foreground">
              Émis par : <span>{affiche.email}</span>
            </p>
          )}
          {affiche.github_url && (
            <p className="text-muted-foreground">
              Issue GitHub :{" "}
              <a
                href={affiche.github_url}
                target="_blank"
                rel="noopener noreferrer"
                className="underline"
              >
                {affiche.github_url}
              </a>
            </p>
          )}
        </div>

        {peutInstruire && (
          <div className="space-y-1.5">
            <Label htmlFor="feedback-statut">Statut</Label>
            <select
              id="feedback-statut"
              className="border-input h-9 w-full rounded-md border bg-transparent px-2 text-sm"
              value={affiche.status}
              disabled={changerStatut.isPending}
              onChange={(e) => changer(e.target.value as Feedback["status"])}
            >
              {Object.entries(LIBELLE_STATUT).map(([valeur, libelle]) => (
                <option key={valeur} value={valeur}>
                  {libelle}
                </option>
              ))}
            </select>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
