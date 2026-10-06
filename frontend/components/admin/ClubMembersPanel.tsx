"use client";
import { useState } from "react";
import { toast } from "sonner";
import { AthleteSearchPicker } from "@/components/admin/AthleteSearchPicker";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useImportClubMembers, useLinkClubMember, useSyncClubMembers } from "@/lib/queries/admin";
import type { ClubMember, ClubMembersSeason } from "@/lib/types";
import { seasonLabel } from "@/lib/utils/season";

const MOTIF: Record<ClubMember["link_status"], string> = {
  auto: "Rattaché",
  manual: "Rattaché à la main",
  unlinked: "Aucune fiche à ce nom",
  ambiguous: "Plusieurs fiches à ce nom",
};

export function ClubMembersPanel({
  season,
  onSeasonChange,
  data,
  isLoading,
}: {
  season: number;
  onSeasonChange: (season: number) => void;
  data: ClubMembersSeason | undefined;
  isLoading: boolean;
}) {
  const relire = useSyncClubMembers();
  const aRattacher = (data?.members ?? []).filter((m) => m.athlete_id === null);
  const saisons = Array.from(new Set([season, ...(data?.seasons ?? [])])).sort((a, b) => b - a);

  return (
    <div className="space-y-6">
      <Card className="space-y-4 p-6">
        <div className="flex flex-wrap items-end gap-4">
          <div className="space-y-2">
            <Label htmlFor="saison-membres">Saison</Label>
            <Select value={String(season)} onValueChange={(v) => onSeasonChange(Number(v))}>
              <SelectTrigger id="saison-membres" className="w-56">
                <SelectValue>{(v) => seasonLabel(Number(v))}</SelectValue>
              </SelectTrigger>
              <SelectContent>
                {saisons.map((s) => (
                  <SelectItem key={s} value={String(s)}>
                    {seasonLabel(s)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button
            onClick={() =>
              relire.mutate(undefined, {
                onSuccess: (r) => {
                  onSeasonChange(r.season);
                  toast.success(`${r.total} licenciés lus pour la ${seasonLabel(r.season).toLowerCase()}.`);
                },
                onError: (erreur: Error) => toast.error(erreur.message),
              })
            }
            disabled={relire.isPending}
          >
            Relire la liste FFTri
          </Button>
        </div>
        {isLoading ? (
          <Skeleton className="h-6 w-64" />
        ) : data ? (
          <p className="text-sm">
            {data.total} licenciés : {data.linked} rattaché{data.linked > 1 ? "s" : ""}, {data.unlinked} sans
            fiche, {data.ambiguous} à départager.
          </p>
        ) : null}
      </Card>

      {aRattacher.length > 0 && (
        <Card className="space-y-3 p-6">
          <h2 className="font-semibold">Licenciés à rattacher</h2>
          <ul className="divide-y">
            {aRattacher.map((membre) => (
              <li key={membre.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                <span>
                  <span className="font-medium">{`${membre.nom} ${membre.prenom}`}</span>
                  <span className="ml-2 text-sm text-[var(--tcn-text-faint)]">{MOTIF[membre.link_status]}</span>
                </span>
                <LienFiche membre={membre} />
              </li>
            ))}
          </ul>
        </Card>
      )}

      <ClubMembersImport defaultSeason={season - 1} />
    </div>
  );
}

function LienFiche({ membre }: { membre: ClubMember }) {
  const [ouvert, setOuvert] = useState(false);
  const rattacher = useLinkClubMember();
  return (
    <>
      <Button variant="outline" size="sm" onClick={() => setOuvert(true)}>
        Rattacher à une fiche
      </Button>
      <Dialog open={ouvert} onOpenChange={setOuvert}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{`Rattacher ${membre.nom} ${membre.prenom}`}</DialogTitle>
            <DialogDescription>
              Choisissez la fiche de cet athlète : ses résultats de la saison compteront pour le club.
            </DialogDescription>
          </DialogHeader>
          <AthleteSearchPicker
            selectedId={null}
            onSelect={(athlete) =>
              rattacher.mutate(
                { memberId: membre.id, athleteId: athlete.id },
                {
                  onSuccess: () => setOuvert(false),
                  onError: (erreur: Error) => toast.error(erreur.message),
                },
              )
            }
          />
        </DialogContent>
      </Dialog>
    </>
  );
}

export function ClubMembersImport({ defaultSeason }: { defaultSeason: number }) {
  const [season, setSeason] = useState(defaultSeason);
  const [fichier, setFichier] = useState<File | null>(null);
  const importer = useImportClubMembers();
  return (
    <Card className="space-y-4 p-6">
      <h2 className="font-semibold">Importer la liste d&apos;une saison passée</h2>
      <p className="text-sm text-[var(--tcn-text-faint)]">
        Un fichier .csv ou .xlsx avec une colonne « Nom » et une colonne « Prénom » (« Sexe » et « Licence » si
        possible). Il remplace toute la liste de la saison choisie.
      </p>
      <div className="flex flex-wrap items-end gap-4">
        <div className="space-y-2">
          <Label htmlFor="saison-import">Saison (année de début)</Label>
          <Input
            id="saison-import"
            type="number"
            value={season}
            onChange={(e) => setSeason(Number(e.target.value))}
            className="w-28"
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="fichier-licencies">Fichier des licenciés (.csv ou .xlsx)</Label>
          <Input
            id="fichier-licencies"
            type="file"
            accept=".csv,.xlsx"
            onChange={(e) => setFichier(e.target.files?.[0] ?? null)}
          />
        </div>
        <Button
          disabled={!fichier || importer.isPending}
          onClick={() =>
            fichier &&
            importer.mutate(
              { season, file: fichier },
              {
                onSuccess: (r) =>
                  toast.success(
                    `${r.total} licenciés importés pour la ${seasonLabel(r.season).toLowerCase()}.`,
                  ),
                onError: (erreur: Error) => toast.error(erreur.message),
              },
            )
          }
        >
          Importer
        </Button>
      </div>
    </Card>
  );
}
