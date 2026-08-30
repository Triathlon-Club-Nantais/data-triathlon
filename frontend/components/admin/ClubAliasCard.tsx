"use client";
import { useRef, useState } from "react";
import { toast } from "sonner";
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
 *
 * Le retrait d'un alias est un geste **neutre** (#499) : aucune donnée
 * détruite, aucun accès fermé — le club retombe sur son libellé brut et se
 * ré-associe en une saisie. Ni couleur destructive ni confirmation, à la
 * différence du retrait d'un libellé TCN (`CounterScopeCard`), dont l'effet
 * immédiat sur les compteurs `scope=club` justifie le traitement lourd.
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

  async function retirerAlias(entree: ClubAlias) {
    try {
      await retirer.mutateAsync(entree.id);
      toast.success(`« ${entree.alias} » retiré de « ${entree.canonical_name} ».`);
      // La ligne — et son bouton, celui qui avait le focus — quitte le DOM :
      // sans ce report, le focus retombe sur `<body>` (même patron que
      // CounterScopeCard, ici sans dialog à fermer d'abord).
      champNomCanonique.current?.focus();
    } catch (e) {
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
          regroupées sous un nom affiché commun. Une orthographe déjà identique au
          nom canonique se fusionne d&apos;elle-même ; seule une orthographe
          <strong> différente</strong> — casse, espacement, abréviation — a besoin
          d&apos;être déclarée ici en alias.
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

        {/* Pas de garde `!isLoading &&` ici : `entrees` vaut `undefined`
            pendant le chargement (`data?.entries` côté appelant), donc
            `groupes` est déjà vide et cette liste ne rend rien tant que
            `isLoading` est vrai — une garde explicite ne change aucun
            comportement, elle ne fait que déclencher un faux positif
            d'eslint-plugin-react-hooks (`react-hooks/refs`) sur le bouton
            de retrait plus bas, qui lit `champNomCanonique.current`. */}
        {Array.from(groupes.entries()).map(([nom, alias_du_groupe]) => (
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
                    variant="outline"
                    size="sm"
                    onClick={() => retirerAlias(entree)}
                    disabled={retirer.isPending}
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
    </Card>
  );
}
