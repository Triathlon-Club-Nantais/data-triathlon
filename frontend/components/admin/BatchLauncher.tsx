"use client";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useBatchRuns, useLaunchBatch } from "@/lib/queries/batches";
import { useSession } from "@/lib/queries/auth";
import type { RescrapeLaunch } from "@/lib/types";

/**
 * Lancement d'une reprise filtrée (#47).
 *
 * **Aucun champ pour la base visée.** Elle vient du réglage de l'instance : un
 * champ ici permettrait à l'administration de la preview d'écrire chez les
 * adhérents, et le backend refuse d'ailleurs un `target` reçu du client.
 *
 * **Aucune liste de fournisseurs non plus.** Le registre vit côté backend, et
 * la copie qu'avait le front avait divergé (cf. `ProviderDetector`). Une saisie
 * libre, validée en amont : le 422 nomme le fautif et énumère les connus.
 */
export function BatchLauncher() {
  const { data: session } = useSession();
  const peutLire = (session?.permissions ?? []).includes("batch:read");
  // N'interroger la liste que si la session sait la lire : sinon l'écran
  // afficherait un bloc en 403 à la place de l'état courant.
  const { data: runs } = useBatchRuns(peutLire);
  const lancer = useLaunchBatch();

  const [provider, setProvider] = useState("");
  const [olderThan, setOlderThan] = useState("");
  const [limit, setLimit] = useState("");
  const [dryRun, setDryRun] = useState(false);

  const enCours = (runs ?? []).some((run) =>
    ["pending", "running"].includes(run.state),
  );

  const soumettre = (evenement: React.FormEvent) => {
    evenement.preventDefault();
    // Les champs vides ne partent pas : `older_than: 0` serait refusé par la
    // borne, et `provider: ""` sélectionnerait un fournisseur nommé « ».
    const options: RescrapeLaunch = { mode: "rescrape", dry_run: dryRun };
    if (provider.trim()) options.provider = provider.trim();
    if (olderThan.trim()) options.older_than = Number(olderThan);
    if (limit.trim()) options.limit = Number(limit);

    lancer.mutate(options, {
      onSuccess: (reponse) =>
        toast.success(`Batch lancé (${reponse.correlation_id}).`),
      // Réaffiché **tel quel** : le backend nomme le fournisseur fautif, la
      // borne dépassée ou le batch déjà en cours. Le réécrire ici perdrait ce
      // qui rend l'erreur réparable.
      onError: (erreur: Error) => toast.error(erreur.message),
    });
  };

  return (
    <Card className="p-6">
      <form className="space-y-4" onSubmit={soumettre}>
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="space-y-2">
            <Label htmlFor="batch-provider">Fournisseur</Label>
            <Input
              id="batch-provider"
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              placeholder="Tous"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="batch-older-than">Ancienneté (jours)</Label>
            <Input
              id="batch-older-than"
              type="number"
              min={1}
              max={3650}
              value={olderThan}
              onChange={(e) => setOlderThan(e.target.value)}
              placeholder="Sans limite"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="batch-limit">Nombre maximum d&apos;épreuves</Label>
            <Input
              id="batch-limit"
              type="number"
              min={1}
              max={500}
              value={limit}
              onChange={(e) => setLimit(e.target.value)}
              placeholder="Sans limite"
            />
          </div>
        </div>

        <div className="flex items-center gap-2">
          <input
            id="batch-dry-run"
            type="checkbox"
            checked={dryRun}
            onChange={(e) => setDryRun(e.target.checked)}
            className="size-4"
          />
          <Label htmlFor="batch-dry-run">
            Simulation — lister les épreuves sans rien écrire
          </Label>
        </div>

        <div className="flex items-center gap-3">
          <Button type="submit" disabled={enCours || lancer.isPending}>
            {lancer.isPending ? "Lancement…" : "Lancer la reprise"}
          </Button>
          {enCours && (
            <p className="text-sm text-muted-foreground">
              Un batch est déjà en cours. Attendez sa fin pour en lancer un autre.
            </p>
          )}
        </div>
      </form>
    </Card>
  );
}
