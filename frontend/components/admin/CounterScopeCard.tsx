"use client";
import { useRef, useState } from "react";
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
 *
 * Le refus de lecture ne se traite **pas** ici : `counter_scope:manage` est le
 * pouvoir unique de la ressource, lecture et écriture confondues, donc un refus
 * rend l'écran entier passif et se dit une fois, au niveau de la page.
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
  nom,
  regle,
  entrees,
  isLoading,
  libelleChamp,
  placeholder,
  descriptionListeVide,
}: {
  kind: ScopeKind;
  titre: string;
  /** Le nom de la liste tel qu'un toast le cite : « ajouté aux {nom} ». */
  nom: string;
  /** La phrase qui dit comment la liste se comporte (FR-015). */
  regle: React.ReactNode;
  entrees: CounterScopeEntry[] | undefined;
  isLoading: boolean;
  libelleChamp: string;
  placeholder: string;
  /**
   * Ce que le vide **signifie** pour cette liste-ci, et non le geste pour en
   * sortir : les deux listes se comportent à l'inverse l'une de l'autre, et
   * c'est vide qu'on a le plus besoin de le savoir.
   */
  descriptionListeVide: React.ReactNode;
}) {
  const ajouter = useAddCounterScopeEntry();
  const retirer = useRemoveCounterScopeEntry();
  const [saisie, setSaisie] = useState("");
  const [aRetirer, setARetirer] = useState<CounterScopeEntry | null>(null);
  const champDAjout = useRef<HTMLInputElement>(null);

  async function soumettre(evenement: React.FormEvent) {
    evenement.preventDefault();
    const valeur = saisie.trim();
    if (!valeur) return;
    try {
      const creee = await ajouter.mutateAsync({ kind, value: valeur });
      setSaisie("");
      toast.success(`« ${creee.value} » ajouté aux ${nom}.`);
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  async function confirmerRetrait() {
    if (!aRetirer) return;
    try {
      await retirer.mutateAsync({ kind, entryId: aRetirer.id });
      toast.success(`« ${aRetirer.value} » retiré des ${nom}.`);
      setARetirer(null);
      // La ligne — et son bouton, celui qui avait le focus — quitte le DOM à la
      // fermeture du dialog : sans cela le focus retombe sur `<body>` et un
      // utilisateur au clavier repart du haut du document à chaque retrait
      // (même patron que `FeedbackTable`).
      champDAjout.current?.focus();
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

  // Le serveur refuse en 409 le retrait du dernier libellé de club
  // (`LastClubLabelError`). Le dire **avant** le clic, en texte visible, plutôt
  // que de laisser ouvrir un dialog qui affirme le contraire et se solde par un
  // toast d'échec — même patron que `GroupsTable` et `RolePermissionsEditor`
  // (#499). Pas d'infobulle : elle n'ouvre ni au tactile, ni sur un bouton
  // désactivé.
  const dernierLibelleDuClub = kind === "club-labels" && entrees?.length === 1;

  const uneDisciplineInconnue = entrees?.some((entree) => !entree.is_known) ?? false;

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
              ref={champDAjout}
              value={saisie}
              onChange={(e) => setSaisie(e.target.value)}
              placeholder={placeholder}
            />
          </div>
          <Button type="submit" disabled={!saisie.trim() || ajouter.isPending}>
            Ajouter
          </Button>
        </form>

        {/* `role="status"` et non `aria-label` seul : porté par un `<div>` sans
            rôle, celui-ci est ignoré des aides techniques et le chargement
            reste muet. */}
        {isLoading && (
          <div role="status">
            <Skeleton className="h-24 w-full" />
            <span className="sr-only">Chargement de la liste</span>
          </div>
        )}

        {!isLoading && entrees?.length === 0 && (
          <EmptyState bare title="Cette liste est vide" description={descriptionListeVide} />
        )}

        {!isLoading && entrees && entrees.length > 0 && (
          <>
            <ul className="divide-y">
              {entrees.map((entree) => (
                <li key={entree.id} className="flex flex-wrap items-center gap-3 py-3">
                  <span className="font-mono text-sm">{entree.value}</span>
                  {!entree.is_known && (
                    // Les couples aplat/encre du thème, comme `PendingBadge` :
                    // la bordure de `variant="outline"` rend 1,22:1 sur le
                    // blanc de la carte, soit aucun signal visuel.
                    <Badge
                      variant="outline"
                      className="border-[var(--tcn-warning-border)] bg-[var(--tcn-warning-bg)] text-[var(--tcn-warning-text)]"
                    >
                      Discipline inconnue
                    </Badge>
                  )}
                  <span className="ml-auto text-xs text-muted-foreground">
                    {entree.created_by
                      ? `Ajouté par ${entree.created_by}, ${timeAgo(entree.created_at)}`
                      : "Configuration initiale"}
                  </span>
                  {dernierLibelleDuClub ? (
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-[var(--tcn-text-faint)]">
                        Dernier libellé — sans lui, plus aucun résultat ne serait du club
                      </span>
                      <Button
                        variant="destructive"
                        size="sm"
                        aria-label={`Retirer « ${entree.value} »`}
                        disabled
                      >
                        Retirer
                      </Button>
                    </div>
                  ) : (
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => setARetirer(entree)}
                      aria-label={`Retirer « ${entree.value} »`}
                    >
                      Retirer
                    </Button>
                  )}
                </li>
              ))}
            </ul>
            {/* La phrase que portait un `title` natif : inatteignable au
                clavier et absente au tactile (#482). Une fois sous la liste
                plutôt qu'une fois par ligne — elle dit la même chose. */}
            {uneDisciplineInconnue && (
              <p className="text-xs text-[var(--tcn-text-faint)]">
                « Discipline inconnue » signale une valeur qui ne correspond à aucune
                discipline connue de l&apos;application. Elle reste exclue des compteurs.
              </p>
            )}
          </>
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
