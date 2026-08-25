"use client";
import { useState } from "react";
import { toast } from "sonner";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { FeedbackDetailDialog } from "@/components/admin/FeedbackDetailDialog";
import { useFeedbackCounts, useFeedbackList, useUpdateFeedbackStatus } from "@/lib/queries/admin";
import { useSession } from "@/lib/queries/auth";
import { messageDeRefus } from "@/lib/api/refus";
import { cn } from "@/lib/utils";
import { formatDate } from "@/lib/utils/date";
import type { Feedback, FeedbackCounts } from "@/lib/types";

const REFUS = { sujet: "retours utilisateurs", action: "consulter les retours utilisateurs" };

type ColonneTriable = "created_at" | "type" | "status";
type Statut = Feedback["status"];
/** Le cinquième filtre n'est pas un statut : il **retire** le paramètre (#500). */
type Filtre = Statut | "tous";

const LIBELLE_STATUT: Record<Statut, string> = {
  nouveau: "Nouveau",
  en_cours: "En cours",
  traite: "Traité",
  ignore: "Ignoré",
};

const STATUTS = Object.keys(LIBELLE_STATUT) as Statut[];

/**
 * Un couple aplat/encre par statut, patron de `BatchRunList` (ADM-3).
 *
 * Le statut s'affichait en texte nu quand le type portait déjà un badge :
 * « Nouveau » et « Ignoré » avaient exactement le même poids visuel, alors que
 * l'un demande un geste et l'autre dit qu'il n'y en aura pas (ADM-10). Les
 * couples sémantiques du thème sont retenus pour la même raison que là-bas :
 * les variantes génériques de `Badge` ne tiennent pas 4,5:1 sous 12 px.
 * L'orange va au seul statut qui bouge encore.
 */
const APLATS: Record<Statut, string> = {
  nouveau: "bg-[var(--tcn-warning-bg)] text-[var(--tcn-warning-text)]",
  en_cours: "bg-[var(--tcn-danger-bg)] text-[var(--tcn-danger-text)]",
  traite: "bg-[var(--tcn-success-bg)] text-[var(--tcn-success-text)]",
  ignore: "bg-[var(--tcn-fill)] text-[var(--tcn-text-faint)]",
};

/**
 * Anneau de focus opaque, la norme du dépôt (`globals.css`, `.tcn-btn`) :
 * l'anneau UA hérité ne vaut que 1,93:1 sur le blanc d'une carte, contre les
 * 3:1 de WCAG 1.4.11.
 */
const FOCUS =
  "focus-visible:outline-2 focus-visible:outline-offset-2 " +
  "focus-visible:outline-[var(--tcn-orange)]";

/**
 * Trois colonnes triables (contracts/feedback-api.md), « Titre » ne l'est pas
 * — le contrat ne l'accepte pas en `sort`, et un clic qui rendrait 422 serait
 * pire qu'un en-tête inerte.
 */
function EnTeteTriable({
  colonne,
  label,
  actif,
  order,
  onTrier,
}: {
  colonne: ColonneTriable;
  label: string;
  actif: boolean;
  order: "asc" | "desc";
  onTrier: (colonne: ColonneTriable) => void;
}) {
  return (
    <TableHead>
      <button type="button" onClick={() => onTrier(colonne)} className={cn("hover:underline", FOCUS)}>
        {label}
        {actif ? (order === "desc" ? " ↓" : " ↑") : ""}
      </button>
    </TableHead>
  );
}

/**
 * La barre de filtres, et **le compteur** : le nombre porté par chaque entrée
 * *est* le « N nouveaux » demandé (ADM-10). Une phrase séparée au-dessus le
 * redirait une seconde fois, et seulement pour un statut sur quatre.
 *
 * Elle reste montée dans tous les états de la liste — chargement, refus,
 * résultat vide —, sans quoi le filtre par défaut serait une impasse : la vue
 * n'ouvre que sur « Nouveau », et un administrateur qui n'en a aucun perdrait
 * l'accès aux trois autres.
 */
function BarreDeStatuts({
  actif,
  comptes,
  onFiltrer,
}: {
  actif: Filtre;
  comptes?: FeedbackCounts;
  onFiltrer: (filtre: Filtre) => void;
}) {
  const entrees: { filtre: Filtre; label: string; compte?: number }[] = [
    ...STATUTS.map((statut) => ({
      filtre: statut as Filtre,
      label: LIBELLE_STATUT[statut],
      compte: comptes?.[statut],
    })),
    { filtre: "tous" as Filtre, label: "Tous", compte: comptes?.total },
  ];

  return (
    <div role="group" aria-label="Filtrer par statut" className="flex flex-wrap gap-2">
      {entrees.map(({ filtre, label, compte }) => (
        <button
          key={filtre}
          type="button"
          aria-pressed={filtre === actif}
          onClick={() => onFiltrer(filtre)}
          className={cn(
            "rounded-full border px-3 py-1.5 text-sm transition-colors",
            FOCUS,
            filtre === actif
              ? "border-[var(--tcn-orange)] bg-[var(--tcn-orange-12)] text-[var(--tcn-text)]"
              : "border-[var(--tcn-border-input)] text-[var(--tcn-text-muted)] hover:bg-[var(--tcn-fill)]",
          )}
        >
          {/* Un seul nœud de texte, décompte compris : deux nœuds feraient du
              libellé du filtre un second « Nouveau » dans la page, à côté du
              badge de la ligne. */}
          {compte === undefined ? label : `${label} · ${compte}`}
        </button>
      ))}
    </div>
  );
}

export function FeedbackTable() {
  const [sort, setSort] = useState<ColonneTriable>("created_at");
  const [order, setOrder] = useState<"asc" | "desc">("desc");
  // La file s'ouvre sur ce qui reste à traiter, pas sur l'historique (ADM-10).
  const [statut, setStatut] = useState<Filtre>("nouveau");
  const [ouvert, setOuvert] = useState<Feedback | null>(null);
  const { data, isLoading, error } = useFeedbackList(sort, order, statut);
  const { data: comptes } = useFeedbackCounts();
  const session = useSession();
  const changerStatut = useUpdateFeedbackStatus();

  // Le serveur reste seul juge : ce test n'autorise rien, il évite d'offrir un
  // contrôle qui rendrait 403.
  const peutInstruire = session.data?.permissions.includes("feedback:manage") ?? false;

  function trier(colonne: ColonneTriable) {
    if (colonne === sort) {
      setOrder(order === "desc" ? "asc" : "desc");
    } else {
      setSort(colonne);
      setOrder("desc");
    }
  }

  async function changer(feedback: Feedback, vers: Statut) {
    try {
      await changerStatut.mutateAsync({ id: feedback.id, status: vers });
      toast.success(`« ${feedback.title} » — ${LIBELLE_STATUT[vers]}.`);
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  const barre = <BarreDeStatuts actif={statut} comptes={comptes} onFiltrer={setStatut} />;

  if (isLoading) {
    return (
      <div className="space-y-4">
        {barre}
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }
  if (error) {
    return (
      <div className="space-y-4">
        {barre}
        <EmptyState {...messageDeRefus(error, REFUS)} />
      </div>
    );
  }
  if (!data || data.length === 0) {
    // Rien du tout et « rien sous ce filtre » sont deux situations distinctes :
    // la première attend des signalements, la seconde attend un clic.
    const baseVide = (comptes?.total ?? 0) === 0;
    return (
      <div className="space-y-4">
        {barre}
        {baseVide ? (
          <EmptyState
            title="Aucun retour utilisateur"
            description="Les signalements soumis depuis le site public apparaîtront ici."
          />
        ) : (
          <EmptyState
            title="Aucun signalement sous ce filtre"
            description="Rien à traiter ici. « Tous » rouvre l'ensemble des signalements."
          />
        )}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {barre}
      <Card className="p-0">
        <Table>
          <TableHeader>
            <TableRow>
              <EnTeteTriable
                colonne="created_at"
                label="Date"
                actif={sort === "created_at"}
                order={order}
                onTrier={trier}
              />
              <EnTeteTriable
                colonne="type"
                label="Type"
                actif={sort === "type"}
                order={order}
                onTrier={trier}
              />
              <TableHead>Titre</TableHead>
              <EnTeteTriable
                colonne="status"
                label="Statut"
                actif={sort === "status"}
                order={order}
                onTrier={trier}
              />
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.map((f) => (
              <TableRow key={f.id}>
                <TableCell>{formatDate(f.created_at)}</TableCell>
                <TableCell>
                  <Badge variant={f.type === "bug" ? "destructive" : "secondary"}>
                    {f.type === "bug" ? "Bug" : "Retour"}
                  </Badge>
                </TableCell>
                <TableCell className="max-w-xs truncate">
                  <Button
                    variant="link"
                    className="h-auto p-0 font-normal"
                    onClick={() => setOuvert(f)}
                  >
                    {f.title}
                  </Button>
                </TableCell>
                <TableCell>
                  {/* Un seul contrôle, coloré : le badge et un sélecteur côte à
                      côte diraient deux fois la même valeur. Qui peut instruire
                      change le statut là où il le lit — instruire dix
                      signalements demandait dix ouvertures de modale. */}
                  {peutInstruire ? (
                    <select
                      aria-label={`Statut de « ${f.title} »`}
                      className={cn(
                        "h-7 rounded-full border-transparent px-2 text-xs font-medium",
                        FOCUS,
                        APLATS[f.status],
                      )}
                      value={f.status}
                      disabled={changerStatut.isPending && changerStatut.variables?.id === f.id}
                      onChange={(e) => changer(f, e.target.value as Statut)}
                    >
                      {STATUTS.map((valeur) => (
                        <option key={valeur} value={valeur}>
                          {LIBELLE_STATUT[valeur]}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <Badge className={APLATS[f.status]}>{LIBELLE_STATUT[f.status]}</Badge>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>
      {ouvert && (
        <FeedbackDetailDialog
          feedback={ouvert}
          open
          onOpenChange={(o) => !o && setOuvert(null)}
        />
      )}
    </div>
  );
}
