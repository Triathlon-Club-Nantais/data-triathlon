"use client";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";
import { useDangerConfirm } from "@/components/admin/DangerConfirm";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useAddMemberEmail, useImportMemberEmails, useRemoveMemberEmail } from "@/lib/queries/admin";
import type { MemberEmail, MemberEmailsImportReport, MemberEmailsSeason } from "@/lib/types";
import { seasonLabel } from "@/lib/utils/season";

function adresses(n: number): string {
  return `${n} adresse${n > 1 ? "s" : ""}`;
}

function compteRendu(r: MemberEmailsImportReport): string {
  const pluriel = (n: number, mot: string) => `${n} ${mot}${n > 1 ? "s" : ""}`;
  return `${pluriel(r.added, "ajoutée")}, ${pluriel(r.removed, "retirée")}, ${pluriel(r.unchanged, "inchangée")}, ${pluriel(r.ignored, "ligne")} ignorée${r.ignored > 1 ? "s" : ""}.`;
}

/**
 * Adresses d'adhérents par saison (#1334). L'import ne remplace que les
 * adresses importées : une adresse ajoutée à la main survit aux imports.
 */
export function MemberEmailsPanel({
  season,
  onSeasonChange,
  data,
  isLoading,
}: {
  season: number;
  onSeasonChange: (season: number) => void;
  data: MemberEmailsSeason | undefined;
  isLoading: boolean;
}) {
  const saisons = Array.from(new Set([season, ...(data?.seasons ?? [])])).sort((a, b) => b - a);

  return (
    <div className="space-y-6">
      <Card className="space-y-4 p-6">
        <div className="space-y-2">
          <Label htmlFor="saison-adresses">Saison</Label>
          <Select value={String(season)} onValueChange={(v) => onSeasonChange(Number(v))}>
            <SelectTrigger id="saison-adresses" className="w-56">
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
        {data && (
          <p className="text-sm">
            {`Saison qui compte aujourd'hui : ${seasonLabel(data.counting_season).toLowerCase()}.`}{" "}
            <span className="text-[var(--tcn-text-faint)]">
              La saison en cours compte dès qu&apos;elle a une adresse importée ; avant le premier import, la liste
              de la saison précédente continue de compter, et les adresses ajoutées à la main pour la saison en
              cours comptent aussi.
            </span>
          </p>
        )}
      </Card>

      <MemberEmailsImport key={season} season={season} />

      <Card className="space-y-4 p-6">
        <h2 className="font-semibold">Adresses de la {seasonLabel(season).toLowerCase()}</h2>
        <AddMemberEmail season={season} />
        {isLoading ? (
          <Skeleton data-testid="member-emails-loading" className="h-24 w-full" />
        ) : data && data.entries.length > 0 ? (
          <>
            <p className="text-sm">{adresses(data.entries.length)}</p>
            <ul className="divide-y">
              {data.entries.map((entry) => (
                <MemberEmailRow key={entry.id} entry={entry} />
              ))}
            </ul>
          </>
        ) : data ? (
          <p className="text-sm text-[var(--tcn-text-faint)]">
            Aucune adresse pour cette saison. Importez l&apos;export AssoConnect, ou ajoutez une adresse à la main.
          </p>
        ) : null}
      </Card>
    </div>
  );
}

function MemberEmailRow({ entry }: { entry: MemberEmail }) {
  const retirer = useRemoveMemberEmail();
  const confirmer = useDangerConfirm();

  async function supprimer() {
    // Destructif : l'adresse cesse aussitôt de reconnaître un adhérent (#499).
    if (
      !(await confirmer({
        titre: `Retirer « ${entry.email} » ?`,
        description: "Cette adresse ne reconnaîtra plus un adhérent pour cette saison.",
        libelleAction: "Retirer",
      }))
    ) {
      return;
    }
    try {
      await retirer.mutateAsync(entry.id);
      toast.success(`${entry.email} est retirée de la liste.`);
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  return (
    <li className="flex flex-wrap items-center justify-between gap-2 py-2">
      <span className="flex flex-wrap items-center gap-2">
        <span className="font-medium">{entry.email}</span>
        <Badge variant={entry.source === "manual" ? "secondary" : "outline"}>
          {entry.source === "manual" ? "Ajoutée à la main" : "Importée"}
        </Badge>
      </span>
      <Button
        variant="destructive"
        size="sm"
        aria-label={`Retirer ${entry.email}`}
        disabled={retirer.isPending}
        onClick={supprimer}
      >
        Retirer
      </Button>
    </li>
  );
}

function AddMemberEmail({ season }: { season: number }) {
  const [saisie, setSaisie] = useState("");
  const ajouter = useAddMemberEmail();

  async function soumettre(e: FormEvent) {
    e.preventDefault();
    try {
      const entry = await ajouter.mutateAsync({ email: saisie, season });
      toast.success(`${entry.email} est ajoutée à la ${seasonLabel(season).toLowerCase()}.`);
      setSaisie("");
    } catch (erreur) {
      toast.error((erreur as Error).message);
    }
  }

  return (
    <div className="@container">
      <form onSubmit={soumettre} className="flex flex-col gap-3 @xl:flex-row @xl:items-end">
        <div className="flex-1 space-y-1.5">
          <Label htmlFor="adresse-adherent">Adresse à ajouter</Label>
          <Input
            id="adresse-adherent"
            type="email"
            placeholder="prenom.nom@exemple.fr"
            value={saisie}
            onChange={(e) => setSaisie(e.target.value)}
          />
        </div>
        <Button type="submit" disabled={!saisie.trim() || ajouter.isPending}>
          Ajouter
        </Button>
      </form>
    </div>
  );
}

function MemberEmailsImport({ season }: { season: number }) {
  const [fichier, setFichier] = useState<File | null>(null);
  const [champ, setChamp] = useState(0);
  const [bilan, setBilan] = useState("");
  const importer = useImportMemberEmails();

  return (
    <Card className="space-y-4 p-6">
      <h2 className="font-semibold">Importer l&apos;export AssoConnect</h2>
      <p className="text-sm text-[var(--tcn-text-faint)]">
        Un fichier .csv ou .xlsx avec une colonne « Email » (ou « E-mail », « Courriel »). Seule cette colonne est lue.
        Il remplace les adresses importées de la {seasonLabel(season).toLowerCase()} ; les adresses ajoutées à la main
        restent.
      </p>
      <div className="flex flex-wrap items-end gap-4">
        <div className="space-y-2">
          <Label htmlFor="fichier-adherents">Export AssoConnect (.csv ou .xlsx)</Label>
          <Input
            key={champ}
            id="fichier-adherents"
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
                onSuccess: (r) => {
                  setBilan(compteRendu(r));
                  toast.success(`Liste de la ${seasonLabel(r.season).toLowerCase()} mise à jour.`);
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
      {/* Région montée en permanence : un contenu injecté plein n'est pas annoncé. */}
      <p role="status" className="text-sm">
        {bilan}
      </p>
    </Card>
  );
}
