"use client";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { formatDate } from "@/lib/utils/date";
import { seasonLabel } from "@/lib/utils/season";
import type { AdminVolunteerActionOut } from "@/lib/types";

/**
 * Détail d'une déclaration de crédit d'athlète (#957) : le tableau tronque
 * titre et description, l'admin les lit ici en entier avant de trancher.
 */
export function AdminVolunteerActionDetailDialog({
  action,
  onOpenChange,
  onAccept,
  onReject,
  disabled,
}: {
  action: AdminVolunteerActionOut | null;
  onOpenChange: (ouvert: boolean) => void;
  onAccept: (id: number) => void;
  onReject: (id: number) => void;
  disabled: boolean;
}) {
  return (
    <Dialog open={action !== null} onOpenChange={onOpenChange}>
      {action && (
        <DialogContent className="flex max-h-[85dvh] flex-col sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle className="break-words pr-8 leading-snug">{action.title ?? "Déclaration sans titre"}</DialogTitle>
            <DialogDescription>
              Déclarée le {formatDate(action.created_at)} · {seasonLabel(action.season)}
            </DialogDescription>
          </DialogHeader>

          {/* Focusable : Safari ne fait défiler au clavier qu'un conteneur qui a le focus. */}
          <div
            role="region"
            aria-label="Contenu de la déclaration"
            tabIndex={0}
            className="min-h-0 space-y-3 overflow-y-auto text-sm"
          >
            <p>
              Athlète :{" "}
              <Link href={`/athletes/${action.athlete_id}`} className="underline underline-offset-2">
                {action.athlete_prenom} {action.athlete_nom}
              </Link>
            </p>
            {action.description ? (
              <p className="whitespace-pre-wrap break-words">{action.description}</p>
            ) : (
              <p className="text-[var(--tcn-text-faint)]">Aucune description.</p>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => onReject(action.id)} disabled={disabled}>
              Refuser
            </Button>
            <Button onClick={() => onAccept(action.id)} disabled={disabled}>
              Accepter
            </Button>
          </DialogFooter>
        </DialogContent>
      )}
    </Dialog>
  );
}
