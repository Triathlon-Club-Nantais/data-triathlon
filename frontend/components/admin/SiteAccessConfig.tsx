"use client";
import { useState } from "react";
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
  useSiteAccessConfig,
  useGenerateSiteAccessPassword,
  useReplaceSiteAccessPassword,
} from "@/lib/queries/admin";
import { timeAgo } from "@/lib/utils/date";

const REFUS = { sujet: "accès au site", action: "gérer l'accès au site" };

/**
 * Gestion admin du mot de passe partagé d'accès au site (#509).
 *
 * Le mot de passe n'est **jamais** relu : ni la saisie manuelle ni la
 * génération ne renvoient un champ pré-rempli, et un mot de passe généré ne
 * s'affiche qu'**une fois**, dans la réponse de son propre appel (FR-003,
 * FR-004) — c'est pourquoi il vit dans un état local `genere`, jamais dans le
 * cache de `useSiteAccessConfig`, qui ne porte que l'état (`configured`,
 * `updated_at`, `updated_by`).
 */
export function SiteAccessConfig() {
  const { data, isLoading, error } = useSiteAccessConfig();
  const remplacer = useReplaceSiteAccessPassword();
  const generer = useGenerateSiteAccessPassword();
  const [saisie, setSaisie] = useState("");
  const [genere, setGenere] = useState<string | null>(null);
  const [confirmation, setConfirmation] = useState(false);

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
      toast.success("Mot de passe du site remplacé.");
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
      toast.success("Mot de passe généré — transmettez-le hors-bande.");
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
    const { title, description } = messageDeRefus(error, REFUS);
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
        <CardTitle>Accès au site</CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        <p className="text-[var(--tcn-text-faint)] text-sm">
          Mot de passe partagé demandé à l&apos;entrée du site. Il est stocké
          haché et salé : personne, y compris un administrateur, ne peut le
          retrouver une fois enregistré — seul un remplacement ou une nouvelle
          génération y change quelque chose.
        </p>

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
            <p className="text-sm font-medium">
              Ce mot de passe ne sera plus jamais affiché — copiez-le maintenant.
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
          className="flex flex-col gap-3 sm:flex-row sm:items-end"
        >
          <div className="flex-1 space-y-1">
            <Label htmlFor="site-password">Nouveau mot de passe</Label>
            <Input
              id="site-password"
              type="text"
              minLength={8}
              value={saisie}
              onChange={(e) => setSaisie(e.target.value)}
              placeholder="Saisir un nouveau mot de passe"
            />
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
            Générer un mot de passe sécurisé
          </Button>
        </form>
      </CardContent>

      <Dialog open={confirmation} onOpenChange={setConfirmation}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Remplacer le mot de passe du site ?</DialogTitle>
            <DialogDescription>
              Toutes les sessions ouvertes cesseront immédiatement d&apos;être
              valides, l&apos;ancien mot de passe compris. Assurez-vous d&apos;avoir
              un moyen de transmettre le nouveau.
            </DialogDescription>
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
