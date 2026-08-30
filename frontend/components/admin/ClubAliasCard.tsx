"use client";
import { useRef, useState } from "react";
import { toast } from "sonner";
import { DangerConfirm } from "@/components/admin/DangerConfirm";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useAddClubAlias, useRemoveClubAlias } from "@/lib/queries/admin";
import type { ClubAlias } from "@/lib/types";
import { timeAgo } from "@/lib/utils/date";

/**
 * Variantes de libellé de club, généralisées à tout club (#635, suite #215).
 *
 * Curation manuelle assistée : aucune suggestion automatique — l'écran ne
 * fait que déclarer des rattachements choisis par l'administrateur, qui les
 * repère par ailleurs (`python -m app.cli club-labels`), comme pour le TCN.
 */
export function ClubAliasCard({
  entrees,
  isLoading,
}: {
  entrees: ClubAlias[] | undefined;
  isLoading: boolean;
}) {
  const ajouter = useAddClubAlias();
  const retirer = useRemoveClubAlias();
  const [nomCanonique, setNomCanonique] = useState("");
  const [alias, setAlias] = useState("");
  const [aRetirer, setARetirer] = useState<ClubAlias | null>(null);
  const champNomCanonique = useRef<HTMLInputElement>(null);

  async function soumettre(evenement?: React.FormEvent) {
    evenement?.preventDefault();
    const nom = nomCanonique.trim();
    const variante = alias.trim();
    if (!nom || !variante) return;
    try {
      await ajouter.mutateAsync({ canonical_name: nom, alias: variante });
      setAlias("");
      toast.success(`« ${variante} » rattaché à « ${nom} ».`);
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  async function confirmerRetrait() {
    if (!aRetirer) return;
    try {
      await retirer.mutateAsync(aRetirer.id);
      toast.success(`« ${aRetirer.alias} » retiré de « ${aRetirer.canonical_name} ».`);
      setARetirer(null);
      champNomCanonique.current?.focus();
    } catch (e) {
      setARetirer(null);
      toast.error((e as Error).message);
    }
  }

  const groupes = new Map<string, ClubAlias[]>();
  for (const entree of entrees ?? []) {
    const liste = groupes.get(entree.canonical_name) ?? [];
    liste.push(entree);
    groupes.set(entree.canonical_name, liste);
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Variantes de libellé de club</CardTitle>
        <p className="text-sm text-muted-foreground">
          Les orthographes sous lesquelles un chronométreur désigne le même club,
          regroupées sous un nom affiché commun. Un club ne fusionne que sous les
          libellés déclarés ici, casse et espacement compris — y compris
          l&apos;orthographe qui correspond déjà au nom canonique, si elle
          apparaît aussi telle quelle en base.
        </p>
      </CardHeader>
      <CardContent className="space-y-6">
        <form onSubmit={soumettre} className="flex flex-wrap items-end gap-3">
          <div className="flex min-w-56 flex-1 flex-col gap-2">
            <Label htmlFor="club-alias-nom">Nom affiché</Label>
            <Input
              id="club-alias-nom"
              ref={champNomCanonique}
              value={nomCanonique}
              onChange={(e) => setNomCanonique(e.target.value)}
              placeholder="Racing Club Nantais"
            />
          </div>
          <div className="flex min-w-56 flex-1 flex-col gap-2">
            <Label htmlFor="club-alias-variante">Libellé brut</Label>
            <Input
              id="club-alias-variante"
              value={alias}
              onChange={(e) => setAlias(e.target.value)}
              placeholder="RACING CLUB NANTAIS"
            />
          </div>
          <Button
            type="submit"
            disabled={!nomCanonique.trim() || !alias.trim() || ajouter.isPending}
          >
            Ajouter
          </Button>
        </form>

        {isLoading && (
          <div role="status">
            <Skeleton className="h-24 w-full" />
            <span className="sr-only">Chargement de la liste</span>
          </div>
        )}

        {!isLoading && groupes.size === 0 && (
          <EmptyState
            bare
            title="Aucune variante déclarée"
            description="Chaque club s'affiche et se filtre sous son libellé brut, verbatim du chronométreur."
          />
        )}

        {!isLoading &&
          Array.from(groupes.entries()).map(([nom, alias_du_groupe]) => (
            <section key={nom} className="space-y-2 border-t pt-4">
              <h3 className="text-sm font-medium">{nom}</h3>
              <ul className="divide-y" aria-label={`Alias de ${nom}`}>
                {alias_du_groupe.map((entree) => (
                  <li key={entree.id} className="flex flex-wrap items-center gap-3 py-3">
                    <span className="font-mono text-sm">{entree.alias}</span>
                    <span className="ml-auto text-xs text-muted-foreground">
                      {entree.created_by
                        ? `Ajouté par ${entree.created_by}, ${timeAgo(entree.created_at)}`
                        : "Configuration initiale"}
                    </span>
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => setARetirer(entree)}
                      aria-label={`Retirer « ${entree.alias} »`}
                    >
                      Retirer
                    </Button>
                  </li>
                ))}
              </ul>
            </section>
          ))}
      </CardContent>

      <DangerConfirm
        open={aRetirer !== null}
        onOpenChange={(ouvert) => !ouvert && setARetirer(null)}
        titre={aRetirer ? `Retirer « ${aRetirer.alias} » ?` : ""}
        description="Ce libellé s'affichera et se filtrera de nouveau sous sa forme brute dès le prochain chargement."
        libelleAction="Retirer"
        enAttente={retirer.isPending}
        onConfirm={confirmerRetrait}
      />
    </Card>
  );
}
