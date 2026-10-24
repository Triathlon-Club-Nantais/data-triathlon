"use client";
import { useState } from "react";
import Link from "next/link";
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
import { UndoList } from "@/components/admin/ArbitrationUndoList";
import {
  useImportClubMembers,
  useLinkClubMember,
  useSyncClubMembers,
  useUnlinkClubMember,
} from "@/lib/queries/admin";
import type { ClubMember, ClubMembersSeason } from "@/lib/types";
import { formatDate } from "@/lib/utils/date";
import { motCompte, plural } from "@/lib/utils/format";
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
  // Les cas à départager d'abord : noyés parmi les sans fiche, on ne les voyait pas.
  const aRattacher = (data?.members ?? [])
    .filter((m) => m.athlete_id === null)
    .sort((a, b) => Number(b.link_status === "ambiguous") - Number(a.link_status === "ambiguous"));
  const saisons = Array.from(new Set([season, ...(data?.seasons ?? [])])).sort((a, b) => b - a);

  return (
    <div className="space-y-6">
      <Card className="space-y-4 p-6">
        <div className="flex flex-wrap items-end gap-4">
          <div className="space-y-2">
            <Label htmlFor="saison-membres">Saison</Label>
            {/* `null` quand l'option retenue quitte la liste, pendant le chargement de la saison choisie. */}
            <Select value={String(season)} onValueChange={(v) => v !== null && onSeasonChange(Number(v))}>
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
                  toast.success(`${motCompte(r.total, "licencié")} ${plural(r.total, "lu")} pour la ${seasonLabel(r.season).toLowerCase()}.`);
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
            {`${motCompte(data.total, "licencié")} : ${motCompte(data.linked, "rattaché")}, ${data.unlinked} sans fiche, ${data.ambiguous} à départager.`}
          </p>
        ) : null}
        {data && data.total === 0 && (
          <p className="text-sm text-[var(--tcn-text-faint)]">
            Aucun licencié pour cette saison. Lancez « Relire la liste FFTri », ou importez un fichier plus bas.
          </p>
        )}
      </Card>

      {data && data.total > 0 && (
        <Card className="space-y-3 p-6">
          <h2 className="font-semibold">Licenciés à rattacher</h2>
          {aRattacher.length === 0 && (
            <p className="text-sm text-[var(--tcn-text-faint)]">Tous les licenciés sont rattachés à une fiche.</p>
          )}
          <ul className="divide-y">
            {aRattacher.map((membre) => (
              <li key={membre.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                <span>
                  <span className="font-medium">{`${membre.nom} ${membre.prenom}`}</span>
                  <span className="ml-2 text-sm text-[var(--tcn-text-faint)]">{MOTIF[membre.link_status]}</span>
                </span>
                <LienFiche membre={membre} />
                {membre.candidates.length > 0 && <Candidates membre={membre} />}
              </li>
            ))}
          </ul>
          <ManualLinks members={data.members.filter((m) => m.link_status === "manual")} />
        </Card>
      )}

      <ClubMembersImport key={season} defaultSeason={season - 1} />
    </div>
  );
}

function ManualLinks({ members }: { members: ClubMember[] }) {
  const unlink = useUnlinkClubMember();
  return (
    <UndoList
      title="Rattachements faits à la main"
      empty="Aucun rattachement fait à la main pour cette saison."
      pending={unlink.isPending}
      items={members.map((m) => ({
        id: m.id,
        label: (
          <>
            {`${m.nom} ${m.prenom} → `}
            <Link href={`/athletes/${m.athlete_id}`} className="tcn-lien-action">
              fiche n° {m.athlete_id}
            </Link>
          </>
        ),
        undoLabel: `Annuler le rattachement de ${m.nom} ${m.prenom}`,
      }))}
      onUndo={(item) =>
        unlink.mutate(item.id, {
          onSuccess: (m) =>
            toast.success(
              m.athlete_id === null
                ? `${m.nom} ${m.prenom} revient dans les licenciés à rattacher.`
                : `${m.nom} ${m.prenom} reprend son rattachement automatique.`,
            ),
          onError: (error: Error) => toast.error(error.message),
        })
      }
    />
  );
}

function Candidates({ membre }: { membre: ClubMember }) {
  const rattacher = useLinkClubMember();
  return (
    <ul className="basis-full space-y-1 border-l-2 border-[var(--tcn-grey-300)] pl-3 text-sm">
      {membre.candidates.map((fiche) => (
        <li key={fiche.athlete_id} className="flex flex-wrap items-center justify-between gap-2">
          <span>
            <Link href={`/athletes/${fiche.athlete_id}`} className="tcn-lien-action">
              fiche n° {fiche.athlete_id}
            </Link>
            {` ${fiche.nom} ${fiche.prenom} · `}
            {fiche.course_name ? (
              <>
                {`${fiche.course_name}${fiche.event_date ? `, ${formatDate(fiche.event_date)}` : ""} · `}
                <span className={fiche.club ? "" : "text-[var(--tcn-text-faint)]"}>
                  {fiche.club ?? "sans club publié"}
                </span>
              </>
            ) : (
              <span className="text-[var(--tcn-text-faint)]">aucun résultat</span>
            )}
          </span>
          <Button
            variant="outline"
            size="sm"
            aria-label={`Rattacher à cette fiche (${membre.nom} ${membre.prenom}, fiche n° ${fiche.athlete_id})`}
            disabled={rattacher.isPending}
            onClick={() =>
              rattacher.mutate(
                { memberId: membre.id, athleteId: fiche.athlete_id },
                {
                  onSuccess: () =>
                    toast.success(`${membre.nom} ${membre.prenom} est rattaché à la fiche n° ${fiche.athlete_id}.`),
                  onError: (erreur: Error) => toast.error(erreur.message),
                },
              )
            }
          >
            Rattacher à cette fiche
          </Button>
        </li>
      ))}
    </ul>
  );
}

function LienFiche({ membre }: { membre: ClubMember }) {
  const [ouvert, setOuvert] = useState(false);
  const rattacher = useLinkClubMember();
  return (
    <>
      <Button
        variant="outline"
        size="sm"
        aria-label={`Rattacher ${membre.nom} ${membre.prenom} à une fiche`}
        disabled={rattacher.isPending}
        onClick={() => setOuvert(true)}
      >
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
                  onSuccess: () => {
                    setOuvert(false);
                    toast.success(`${membre.nom} ${membre.prenom} est rattaché à la fiche choisie.`);
                  },
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
  const [season, setSeason] = useState(String(defaultSeason));
  const [fichier, setFichier] = useState<File | null>(null);
  const [champ, setChamp] = useState(0);
  const saisonValide = Number.isInteger(Number(season)) && season.trim() !== "";
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
            onChange={(e) => setSeason(e.target.value)}
            className="w-28"
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="fichier-licencies">Fichier des licenciés (.csv ou .xlsx)</Label>
          <Input
            key={champ}
            id="fichier-licencies"
            type="file"
            accept=".csv,.xlsx"
            onChange={(e) => setFichier(e.target.files?.[0] ?? null)}
          />
        </div>
        <Button
          disabled={!fichier || !saisonValide || importer.isPending}
          onClick={() =>
            fichier &&
            importer.mutate(
              { season: Number(season), file: fichier },
              {
                onSuccess: (r) => {
                  toast.success(
                    `${motCompte(r.total, "licencié")} ${plural(r.total, "importé")} pour la ${seasonLabel(r.season).toLowerCase()}.`,
                  );
                  setFichier(null);
                  setChamp((n) => n + 1);
                },
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
