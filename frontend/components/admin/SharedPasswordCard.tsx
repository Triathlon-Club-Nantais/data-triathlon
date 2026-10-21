"use client";
import { useState, type ReactNode } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { messageDeRefus } from "@/lib/api/refus";
import {
  useGenerateSharedPassword,
  useReplaceSharedPassword,
  useSharedPasswordConfig,
  type SharedPasswordKind,
} from "@/lib/queries/admin";
import { timeAgo } from "@/lib/utils/date";

/** Les textes propres à chaque carte ; le reste du rendu est commun. */
export interface SharedPasswordCopy {
  title: string;
  description: ReactNode;
  label: string;
  placeholder: string;
  generateLabel: string;
  generatedWarning: string;
  replacedToast: string;
  generatedToast: string;
  dialogTitle: string;
  dialogDescription: ReactNode;
}

interface SharedPasswordCardProps {
  kind: SharedPasswordKind;
  inputId: string;
  minLength: number;
  refus: Parameters<typeof messageDeRefus>[1];
  copy: SharedPasswordCopy;
  /** Aide sous le champ, reliée par `aria-describedby`. */
  help?: ReactNode;
}

/**
 * Carte admin d'un mot de passe partagé (accès au site #509, page bénévoles
 * #271), factorisée par #1583.
 *
 * Le mot de passe n'est **jamais** relu : ni la saisie manuelle ni la
 * génération ne renvoient un champ pré-rempli, et un mot de passe généré ne
 * s'affiche qu'**une fois**, dans la réponse de son propre appel (FR-003,
 * FR-004). C'est pourquoi il vit dans un état local `genere`, jamais dans le
 * cache de `useSharedPasswordConfig`, qui ne porte que l'état (`configured`,
 * `updated_at`, `updated_by`).
 */
export function SharedPasswordCard({
  kind,
  inputId,
  minLength,
  refus,
  copy,
  help,
}: SharedPasswordCardProps) {
  const { data, isLoading, error } = useSharedPasswordConfig(kind);
  const remplacer = useReplaceSharedPassword(kind);
  const generer = useGenerateSharedPassword(kind);
  const [saisie, setSaisie] = useState("");
  const [genere, setGenere] = useState<string | null>(null);
  const [confirmation, setConfirmation] = useState(false);
  const aideId = `${inputId}-aide`;

  function demanderConfirmation(evenement: React.SyntheticEvent) {
    evenement.preventDefault();
    if (!saisie.trim()) return;
    setConfirmation(true);
  }

  async function confirmerRemplacement() {
    const mot_de_passe = saisie.trim();
    try {
      await remplacer.mutateAsync(mot_de_passe);
      setSaisie("");
      setGenere(null);
      setConfirmation(false);
      toast.success(copy.replacedToast);
    } catch (e) {
      setConfirmation(false);
      toast.error((e as Error).message);
    }
  }

  async function declencherGeneration() {
    try {
      const resultat = await generer.mutateAsync();
      setGenere(resultat.password);
      setSaisie("");
      toast.success(copy.generatedToast);
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  async function copier() {
    if (!genere) return;
    await navigator.clipboard.writeText(genere);
    toast.success("Copié dans le presse-papiers.");
  }

  if (error) {
    const { title, description } = messageDeRefus(error, refus);
    return (
      <Card>
        <CardHeader>
          <CardTitle>{title}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-[var(--tcn-text-faint)] text-sm">{description}</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{copy.title}</CardTitle>
      </CardHeader>
      <CardContent className="@container space-y-6">
        <p className="text-[var(--tcn-text-faint)] text-sm">{copy.description}</p>

        {!isLoading && data && (
          <div className="flex items-center gap-2 text-sm">
            {data.configured ? (
              <>
                <Badge variant="secondary">Configuré</Badge>
                <span className="text-[var(--tcn-text-faint)]">
                  {data.updated_by && `par ${data.updated_by}`}
                  {data.updated_at && ` — ${timeAgo(data.updated_at)}`}
                </span>
              </>
            ) : (
              <Badge variant="outline">Non configuré</Badge>
            )}
          </div>
        )}

        {genere && (
          <div
            role="alert"
            className="space-y-2 rounded-md border p-4"
            style={{ borderColor: "var(--tcn-warning-border)", background: "var(--tcn-warning-bg)" }}
          >
            <p className="text-sm font-medium" style={{ color: "var(--tcn-warning-text)" }}>
              {copy.generatedWarning}
            </p>
            <div className="flex items-center gap-2">
              <code className="rounded bg-black/10 px-2 py-1 text-sm">{genere}</code>
              <Button type="button" variant="outline" size="sm" onClick={copier}>
                Copier
              </Button>
            </div>
          </div>
        )}

        <form
          onSubmit={demanderConfirmation}
          className="flex flex-col gap-3 @xl:flex-row @xl:items-end"
        >
          <div className="flex-1 space-y-1">
            <Label htmlFor={inputId}>{copy.label}</Label>
            <Input
              id={inputId}
              type="text"
              minLength={minLength}
              aria-describedby={help ? aideId : undefined}
              value={saisie}
              onChange={(e) => setSaisie(e.target.value)}
              placeholder={copy.placeholder}
            />
            {help && (
              <p id={aideId} className="text-xs text-muted-foreground">
                {help}
              </p>
            )}
          </div>
          <Button type="submit" disabled={remplacer.isPending || !saisie.trim()}>
            Remplacer
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={declencherGeneration}
            disabled={generer.isPending}
          >
            {copy.generateLabel}
          </Button>
        </form>
      </CardContent>

      <Dialog open={confirmation} onOpenChange={setConfirmation}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{copy.dialogTitle}</DialogTitle>
            <DialogDescription>{copy.dialogDescription}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmation(false)}>
              Renoncer
            </Button>
            <Button onClick={confirmerRemplacement} disabled={remplacer.isPending}>
              Remplacer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
