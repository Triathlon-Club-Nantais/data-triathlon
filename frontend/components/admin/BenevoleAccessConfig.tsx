"use client";
import { useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { messageDeRefus } from "@/lib/api/refus";
import {
  useBenevoleAccessConfig,
  useGenerateBenevoleAccessPassword,
  useReplaceBenevoleAccessPassword,
} from "@/lib/queries/admin";
import { timeAgo } from "@/lib/utils/date";

const REFUS = { sujet: "accès bénévoles", action: "gérer l'accès bénévoles" };

/**
 * Gestion admin du mot de passe partagé de la page bénévoles (#271 →
 * `specs/20260815-173645-admin-mdp-benevoles/`).
 *
 * Le mot de passe n'est **jamais** relu : ni la saisie manuelle ni la
 * génération ne renvoient un champ pré-rempli, et un mot de passe généré ne
 * s'affiche qu'**une fois**, dans la réponse de son propre appel (FR-003,
 * FR-004) — c'est pourquoi il vit dans un état local `genere`, jamais dans le
 * cache de `useBenevoleAccessConfig`, qui ne porte que l'état (`configured`,
 * `updated_at`, `updated_by`).
 */
export function BenevoleAccessConfig() {
  const { data, isLoading, error } = useBenevoleAccessConfig();
  const remplacer = useReplaceBenevoleAccessPassword();
  const generer = useGenerateBenevoleAccessPassword();
  const [saisie, setSaisie] = useState("");
  const [genere, setGenere] = useState<string | null>(null);

  async function soumettre(evenement: React.SyntheticEvent) {
    evenement.preventDefault();
    const mot_de_passe = saisie.trim();
    if (!mot_de_passe) return;
    try {
      await remplacer.mutateAsync(mot_de_passe);
      setSaisie("");
      setGenere(null);
      toast.success("Mot de passe bénévoles remplacé.");
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  async function declencherGeneration() {
    try {
      const resultat = await generer.mutateAsync();
      setGenere(resultat.password);
      setSaisie("");
      toast.success("Mot de passe généré — transmettez-le aux bénévoles hors-bande.");
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
        <CardTitle>Accès bénévoles</CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        <p className="text-[var(--tcn-text-faint)] text-sm">
          Mot de passe partagé de la page de vérification des résultats par
          les bénévoles. Il est stocké haché et salé : personne, y compris un
          administrateur, ne peut le retrouver une fois enregistré — seul un
          remplacement ou une nouvelle génération y change quelque chose.
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
            className="space-y-2 rounded-md border border-amber-500/40 bg-amber-500/10 p-4"
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

        <form onSubmit={soumettre} className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="flex-1 space-y-1">
            <Label htmlFor="benevole-password">Nouveau mot de passe</Label>
            <Input
              id="benevole-password"
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
    </Card>
  );
}
