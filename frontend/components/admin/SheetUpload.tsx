"use client";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiClient } from "@/lib/api/client";
import type { BatchLaunched, SheetColumns } from "@/lib/types";

/**
 * Import d'un fichier de résultats (#47) — remplace le Google Sheet côté écran.
 *
 * Deux temps, un seul fichier : téléverser pour voir les colonnes, puis
 * désigner celle qui porte les liens. **Le fichier reste dans le navigateur**
 * entre les deux appels — il n'est jamais stocké côté serveur (FR-011), ce qui
 * évite un dépôt temporaire et la question de sa purge.
 */
export function SheetUpload() {
  const [fichier, setFichier] = useState<File | null>(null);
  const [colonnes, setColonnes] = useState<SheetColumns | null>(null);
  const [colonne, setColonne] = useState<number | null>(null);
  const [dryRun, setDryRun] = useState(false);
  const [lance, setLance] = useState<BatchLaunched | null>(null);

  const lire = useMutation({
    mutationFn: (f: File) => apiClient.readSheetColumns(f),
    onSuccess: (data) => {
      setColonnes(data);
      // `null` quand aucune colonne ne porte de lien : on ne présélectionne
      // alors rien, et l'écran le dit. Deviner ferait lancer sur la mauvaise.
      setColonne(data.suggested_index);
      setLance(null);
    },
    // Le motif du serveur, tel quel : il distingue « format non pris en
    // charge » de « trop volumineux » et de « fichier illisible ».
    onError: (erreur: Error) => {
      setColonnes(null);
      toast.error(erreur.message);
    },
  });

  const lancer = useMutation({
    mutationFn: () =>
      apiClient.launchBatchFromFile(fichier as File, colonne as number, dryRun),
    onSuccess: setLance,
    onError: (erreur: Error) => toast.error(erreur.message),
  });

  const choisirFichier = (e: React.ChangeEvent<HTMLInputElement>) => {
    const choisi = e.target.files?.[0] ?? null;
    setFichier(choisi);
    setColonnes(null);
    setColonne(null);
    if (choisi) lire.mutate(choisi);
  };

  const ignores = Object.entries(lance?.ignored_by_host ?? {});

  return (
    <Card className="space-y-4 p-6">
      <div className="space-y-2">
        <Label htmlFor="sheet-file">Fichier de résultats (.csv ou .xlsx)</Label>
        <Input
          id="sheet-file"
          type="file"
          accept=".csv,.xlsx"
          onChange={choisirFichier}
        />
      </div>

      {lire.isPending && (
        <p className="text-sm text-muted-foreground">Lecture du fichier…</p>
      )}

      {colonnes && (
        <>
          <div className="space-y-2">
            <Label htmlFor="sheet-column">Colonne des liens de résultats</Label>
            <select
              id="sheet-column"
              className="h-9 w-full rounded-md border bg-transparent px-3 text-sm"
              value={colonne ?? ""}
              onChange={(e) => setColonne(Number(e.target.value))}
            >
              <option value="" disabled>
                Choisir une colonne
              </option>
              {colonnes.columns.map((c) => (
                <option key={c.index} value={c.index}>
                  {c.header} —{" "}
                  {c.link_count ? `${c.link_count} liens` : "aucun lien"}
                </option>
              ))}
            </select>
            <p className="text-sm text-muted-foreground">
              {colonnes.row_count} lignes lues.
            </p>
          </div>

          {colonnes.suggested_index === null && (
            // Le cas d'un classeur dont les liens sont des hyperliens sans
            // texte (D8) : le dire vaut mieux que présélectionner au hasard.
            <p className="text-sm text-muted-foreground">
              Aucune colonne ne semble porter de lien. Si le fichier en contient,
              ce sont peut-être des hyperliens sans texte : recopiez les adresses
              en clair dans une colonne.
            </p>
          )}

          <div className="flex items-center gap-2">
            <input
              id="sheet-dry-run"
              type="checkbox"
              checked={dryRun}
              onChange={(e) => setDryRun(e.target.checked)}
              className="size-4"
            />
            <Label htmlFor="sheet-dry-run">
              Simulation — lister les épreuves sans rien écrire
            </Label>
          </div>

          <Button
            onClick={() => lancer.mutate()}
            disabled={colonne === null || lancer.isPending}
          >
            {lancer.isPending ? "Lancement…" : "Lancer l'import"}
          </Button>
        </>
      )}

      {lance && (
        <div className="space-y-1 text-sm">
          <p>
            Import lancé ({lance.correlation_id}) — {lance.epreuves} épreuves.
          </p>
          {ignores.length > 0 && (
            // Ni un succès ni un échec : ces liens ne partiront pas. Les taire
            // ferait chercher des épreuves manquantes dans le bilan.
            <p className="text-muted-foreground">
              Liens écartés, aucun scraper ne les reconnaît :{" "}
              {ignores.map(([hote, n]) => `${hote} (${n})`).join(", ")}.
            </p>
          )}
        </div>
      )}
    </Card>
  );
}
