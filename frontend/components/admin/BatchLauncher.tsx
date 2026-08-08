"use client";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { providerLabel } from "@/lib/constants";
import { useBatchRuns, useLaunchBatch, useProviders } from "@/lib/queries/batches";
import { useSession } from "@/lib/queries/auth";
import type { RescrapeLaunch } from "@/lib/types";

/** Valeur du choix « tous les fournisseurs » : `""` n'est pas une valeur de Select. */
const TOUS = "all";

/**
 * Lancement d'une reprise filtrée (#47).
 *
 * **Aucun champ pour la base visée.** Elle vient du réglage de l'instance : un
 * champ ici permettrait à l'administration de la preview d'écrire chez les
 * adhérents, et le backend refuse d'ailleurs un `target` reçu du client.
 *
 * **Le fournisseur se choisit dans une liste, mais le front n'en tient aucune.**
 * Elle vient de `GET /scrape/providers`, donc du même registre que la
 * validation du lancement : impossible de proposer un nom que le batch
 * refuserait, ou d'ignorer un provider ajouté depuis (la copie en dur qu'avait
 * le front avait divergé, cf. `ProviderDetector`). Le 422 reste utile : il
 * nomme le fautif si l'API refuse malgré tout.
 */
export function BatchLauncher() {
  const { data: session } = useSession();
  const peutLire = (session?.permissions ?? []).includes("batch:read");
  // N'interroger la liste que si la session sait la lire : sinon l'écran
  // afficherait un bloc en 403 à la place de l'état courant.
  const { data: runs } = useBatchRuns(peutLire);
  const { data: providers } = useProviders();
  const lancer = useLaunchBatch();

  const [provider, setProvider] = useState(TOUS);
  const [olderThan, setOlderThan] = useState("");
  const [limit, setLimit] = useState("");
  const [dryRun, setDryRun] = useState(false);

  const enCours = (runs ?? []).some((run) =>
    ["pending", "running"].includes(run.state),
  );

  const soumettre = (evenement: React.FormEvent) => {
    evenement.preventDefault();
    // Les champs vides ne partent pas : `older_than: 0` serait refusé par la
    // borne, et « Tous » n'est pas un fournisseur.
    const options: RescrapeLaunch = { mode: "rescrape", dry_run: dryRun };
    if (provider !== TOUS) options.provider = provider;
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
            <Select value={provider} onValueChange={(v) => setProvider(v as string)}>
              <SelectTrigger id="batch-provider" className="w-full">
                <SelectValue>
                  {(v) => (v === TOUS ? "Tous" : providerLabel(v as string))}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={TOUS}>Tous</SelectItem>
                {(providers ?? []).map((nom) => (
                  <SelectItem key={nom} value={nom}>
                    {providerLabel(nom)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
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
