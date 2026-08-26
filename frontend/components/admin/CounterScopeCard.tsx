"use client";
import { useState } from "react";
import { toast } from "sonner";
import { DangerConfirm } from "@/components/admin/DangerConfirm";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { CLUB_NAME } from "@/lib/club";
import { messageDeRefus } from "@/lib/api/refus";
import {
  useAddCounterScopeEntry,
  useRemoveCounterScopeEntry,
} from "@/lib/queries/admin";
import type { CounterScopeEntry, ScopeKind } from "@/lib/types";
import { timeAgo } from "@/lib/utils/date";

/**
 * Une des deux listes qui bornent les compteurs (#95).
 *
 * Un seul composant, monté deux fois : les deux natures ont exactement la même
 * forme — une chaîne, sa provenance, un ajout, un retrait — et seuls changent
 * les mots qui l'entourent. Deux composants jumeaux auraient divergé au premier
 * ajustement d'un des deux.
 */

/**
 * Miroir minimal de `normalize_club` côté serveur : casse et espaces aplatis.
 *
 * **Il ne décide de rien** — le verdict appartient au serveur, qui normalise à
 * l'écriture. Il ne sert qu'à reconnaître, avant d'envoyer, que la valeur
 * retirée est celle du nom affiché du club, pour le dire dans la confirmation.
 * Un écart entre les deux normalisations ne produirait qu'un avertissement
 * manquant, jamais une donnée fausse.
 */
function formeComparable(valeur: string): string {
  return valeur.replace(/\s+/g, " ").trim().toLowerCase();
}

export function CounterScopeCard({
  kind,
  titre,
  regle,
  entrees,
  isLoading,
  error,
  libelleChamp,
  placeholder,
}: {
  kind: ScopeKind;
  titre: string;
  /** La phrase qui dit comment la liste se comporte (FR-015). */
  regle: React.ReactNode;
  entrees: CounterScopeEntry[] | undefined;
  isLoading: boolean;
  error: Error | null;
  libelleChamp: string;
  placeholder: string;
}) {
  const ajouter = useAddCounterScopeEntry();
  const retirer = useRemoveCounterScopeEntry();
  const [saisie, setSaisie] = useState("");
  const [aRetirer, setARetirer] = useState<CounterScopeEntry | null>(null);

  async function soumettre(evenement: React.FormEvent) {
    evenement.preventDefault();
    const valeur = saisie.trim();
    if (!valeur) return;
    try {
      const creee = await ajouter.mutateAsync({ kind, value: valeur });
      setSaisie("");
      toast.success(`« ${creee.value} » ajouté.`);
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  async function confirmerRetrait() {
    if (!aRetirer) return;
    try {
      await retirer.mutateAsync({ kind, entryId: aRetirer.id });
      toast.success(`« ${aRetirer.value} » retiré.`);
      setARetirer(null);
    } catch (e) {
      setARetirer(null);
      toast.error((e as Error).message);
    }
  }

  // Retirer le libellé qui correspond au nom affiché du club est cohérent en
  // soi — le club peut n'avoir jamais été écrit ainsi par un chronométreur —
  // mais c'est le cas où l'on se trompe le plus facilement : plus rien portant
  // le nom du club ne serait compté.
  const retireLeNomDuClub =
    kind === "club-labels" &&
    aRetirer !== null &&
    formeComparable(aRetirer.value) === formeComparable(CLUB_NAME);

  return (
    <Card>
      <CardHeader>
        <CardTitle>{titre}</CardTitle>
        <p className="text-sm text-muted-foreground">{regle}</p>
      </CardHeader>
      <CardContent className="space-y-6">
        <form onSubmit={soumettre} className="flex flex-wrap items-end gap-3">
          <div className="min-w-56 flex-1 space-y-2">
            <Label htmlFor={`ajout-${kind}`}>{libelleChamp}</Label>
            <Input
              id={`ajout-${kind}`}
              value={saisie}
              onChange={(e) => setSaisie(e.target.value)}
              placeholder={placeholder}
            />
          </div>
          <Button type="submit" disabled={!saisie.trim() || ajouter.isPending}>
            Ajouter
          </Button>
        </form>

        {isLoading && <Skeleton className="h-24 w-full" aria-label="Chargement de la liste" />}

        {error && (
          <EmptyState bare {...messageDeRefus(error, {
            sujet: "réglages de la portée des compteurs",
            action: "gérer la portée des compteurs",
          })} />
        )}

        {!isLoading && !error && entrees?.length === 0 && (
          <EmptyState
            bare
            title="Cette liste est vide"
            description="Ajoutez une entrée ci-dessus pour la remplir."
          />
        )}

        {!isLoading && !error && entrees && entrees.length > 0 && (
          <ul className="divide-y">
            {entrees.map((entree) => (
              <li key={entree.id} className="flex flex-wrap items-center gap-3 py-3">
                <span className="font-mono text-sm">{entree.value}</span>
                {!entree.is_known && (
                  <Badge variant="outline" title="Cette discipline ne correspond à aucune discipline connue de l'application.">
                    Discipline inconnue
                  </Badge>
                )}
                <span className="ml-auto text-xs text-muted-foreground">
                  {entree.created_by
                    ? `Ajouté par ${entree.created_by}, ${timeAgo(entree.created_at)}`
                    : "Configuration initiale"}
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setARetirer(entree)}
                  aria-label={`Retirer « ${entree.value} »`}
                >
                  Retirer
                </Button>
              </li>
            ))}
          </ul>
        )}
      </CardContent>

      <DangerConfirm
        open={aRetirer !== null}
        onOpenChange={(ouvert) => !ouvert && setARetirer(null)}
        titre={aRetirer ? `Retirer « ${aRetirer.value} » ?` : ""}
        description={
          kind === "club-labels"
            ? "Les résultats portant ce libellé sortiront des compteurs du club dès le prochain chargement."
            : "Cette discipline rentrera dans les compteurs de triathlon dès le prochain chargement."
        }
        avertissement={
          retireLeNomDuClub
            ? `C'est le libellé qui correspond au nom affiché du club. Une fois retiré, un résultat écrit « ${CLUB_NAME} » ne sera plus compté comme un résultat du club.`
            : undefined
        }
        libelleAction="Retirer"
        enAttente={retirer.isPending}
        onConfirm={confirmerRetrait}
      />
    </Card>
  );
}
