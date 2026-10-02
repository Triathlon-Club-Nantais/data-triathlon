"use client";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useDangerConfirm } from "@/components/admin/DangerConfirm";
import { apiClient } from "@/lib/api/client";
import { messageDeRefus } from "@/lib/api/refus";
import { useApplyOpposition, useOppositions } from "@/lib/queries/admin";
import { formatDate, localToday } from "@/lib/utils/date";

const REFUS = { sujet: "oppositions", action: "consulter les oppositions" };

/**
 * Droit d'opposition (#334) : la preuve du délai d'un mois, et l'enregistrement par nom
 * d'une personne qui n'a encore aucune fiche. Aucun nom n'est affiché : la base n'en garde pas.
 */
export function OppositionsScreen() {
  const { data, isLoading, error } = useOppositions();
  const appliquer = useApplyOpposition();
  const confirmer = useDangerConfirm();
  const [nom, setNom] = useState("");
  const [prenom, setPrenom] = useState("");
  const [demande, setDemande] = useState(localToday());

  async function enregistrer(evenement: React.SyntheticEvent) {
    evenement.preventDefault();
    if (!nom.trim() || !prenom.trim()) return;
    const identite = { nom: nom.trim(), prenom: prenom.trim() };
    try {
      const apercu = await apiClient.previewOpposition(identite);
      const homonymes =
        apercu.athletes > 1 ? ` ${apercu.athletes} fiches portent ce nom, elles seront toutes anonymisées.` : "";
      const accord = await confirmer({
        titre: `Anonymiser ${identite.prenom} ${identite.nom} ?`,
        description: `${apercu.results} résultat${apercu.results > 1 ? "s" : ""} concerné${apercu.results > 1 ? "s" : ""}.${homonymes} Ce geste est définitif, et tout résultat importé ensuite à ce nom arrivera anonyme.`,
        libelleAction: "Anonymiser définitivement",
      });
      if (!accord) return;
      await appliquer.mutateAsync({ ...identite, requested_on: demande });
      setNom("");
      setPrenom("");
      toast.success("Opposition enregistrée.");
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  return (
    <div className="space-y-6">
      <Card className="space-y-3 p-4">
        <div className="font-bold">Enregistrer une opposition par nom</div>
        <p className="text-[var(--tcn-text-faint)] text-sm">
          Pour une personne qui n&apos;a pas encore de fiche, ou depuis une demande reçue par courrier. Si une
          fiche existe, ses résultats sont anonymisés tout de suite.
        </p>
        <form onSubmit={enregistrer} className="grid gap-3 sm:grid-cols-4 sm:items-end">
          <div className="space-y-1.5">
            <Label htmlFor="opposition-nom">Nom</Label>
            <Input id="opposition-nom" value={nom} onChange={(e) => setNom(e.target.value)} autoComplete="off" />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="opposition-prenom">Prénom</Label>
            <Input
              id="opposition-prenom"
              value={prenom}
              onChange={(e) => setPrenom(e.target.value)}
              autoComplete="off"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="opposition-date">Date de la demande</Label>
            <Input
              id="opposition-date"
              type="date"
              max={localToday()}
              required
              value={demande}
              onChange={(e) => setDemande(e.target.value)}
            />
          </div>
          <Button type="submit" disabled={appliquer.isPending}>
            Enregistrer l&apos;opposition
          </Button>
        </form>
      </Card>

      {isLoading ? (
        <Skeleton className="h-40 w-full" />
      ) : error ? (
        <EmptyState {...messageDeRefus(error, REFUS)} />
      ) : !data || data.length === 0 ? (
        <EmptyState
          title="Aucune opposition"
          description="Les oppositions appliquées apparaîtront ici, avec leur délai de traitement."
        />
      ) : (
        <Card className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Demande</TableHead>
                <TableHead>Application</TableHead>
                <TableHead>Délai</TableHead>
                <TableHead>Appliquée par</TableHead>
                <TableHead>Résultats anonymisés</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.map((opposition) => (
                <TableRow key={opposition.id}>
                  <TableCell>{formatDate(opposition.requested_on)}</TableCell>
                  <TableCell>{formatDate(opposition.applied_at)}</TableCell>
                  <TableCell>
                    <span>{opposition.delay_days} jour{opposition.delay_days > 1 ? "s" : ""}</span>
                    {opposition.overdue && (
                      <span className="ml-2 font-semibold text-[var(--tcn-danger-text)]">hors délai légal</span>
                    )}
                  </TableCell>
                  <TableCell>{opposition.applied_by_name ?? "—"}</TableCell>
                  <TableCell>{opposition.anonymised_count}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}
    </div>
  );
}
