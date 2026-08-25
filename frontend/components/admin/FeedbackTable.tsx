"use client";
import { useRef, useState } from "react";
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

/** Le titre, ramené à ce qui distingue une ligne d'une autre à l'oreille. */
function abrege(titre: string): string {
  return titre.length <= 60 ? titre : `${titre.slice(0, 60).trimEnd()}…`;
}

/**
 * Un couple aplat/encre par statut, patron de `BatchRunList` (ADM-3).
 *
 * Le statut s'affichait en texte nu quand le type portait déjà un badge :
 * « Nouveau » et « Ignoré » avaient exactement le même poids visuel, alors que
 * l'un demande un geste et l'autre dit qu'il n'y en aura pas (ADM-10). Les
 * couples sémantiques du thème sont retenus pour la même raison que là-bas :
 * les variantes génériques de `Badge` ne tiennent pas 4,5:1 sous 12 px.
 *
 * **L'accent le plus fort va à `nouveau`**, le seul statut qui demande un
 * geste — et c'est en vue « Tous » que la couleur travaille, la vue par défaut
 * n'affichant qu'un statut. `--tcn-danger` n'est pas un rouge ici : c'est
 * l'orange de marque (`#E9530E`), ce que `globals.css` nomme
 * « danger / doublon ». Le jaune de `--tcn-warning` va donc à `en_cours`, et
 * l'inverse — l'orange sur `en_cours` — mettrait l'accent sur ce qui est déjà
 * pris en main.
 */
const APLATS: Record<Statut, string> = {
  nouveau: "bg-[var(--tcn-danger-bg)] text-[var(--tcn-danger-text)]",
  en_cours: "bg-[var(--tcn-warning-bg)] text-[var(--tcn-warning-text)]",
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
  refActif,
}: {
  actif: Filtre;
  comptes?: FeedbackCounts;
  onFiltrer: (filtre: Filtre) => void;
  refActif?: React.RefObject<HTMLButtonElement | null>;
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
          ref={filtre === actif ? refActif : undefined}
          aria-pressed={filtre === actif}
          onClick={() => onFiltrer(filtre)}
          className={cn(
            // `cursor-pointer` est la norme du dépôt (`ui/button.tsx`) : sans
            // lui, un bouton n'annonce pas qu'il est cliquable — et ces
            // puces-ci n'ont que du texte gris pour le dire.
            "cursor-pointer rounded-full border px-3 py-1.5 text-sm transition-colors",
            FOCUS,
            filtre === actif
              ? "border-[var(--tcn-orange)] bg-[var(--tcn-orange-12)] text-[var(--tcn-text)]"
              : // Le survol prend une teinte orange et non `--tcn-fill` : celui-ci
                // vaut **exactement** `--background` (`#f4f3f0`), donc un survol à
                // 1,00:1 — le même piège que le `bg-muted` des squelettes.
                "border-[var(--tcn-grey-400)] text-[var(--tcn-text-muted)] " +
                "hover:bg-[var(--tcn-orange-08)] hover:text-[var(--tcn-text)]",
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
  // Les lignes dont le changement de statut est en vol. Un `useMutation` est
  // **partagé** par tout le tableau et ses `variables` ne portent que le dernier
  // appel : s'y fier réactiverait la ligne A dès qu'on touche la ligne B.
  const [enVol, setEnVol] = useState<number[]>([]);
  const filtreActif = useRef<HTMLButtonElement | null>(null);
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
    if (enVol.includes(feedback.id)) return;
    // Le contrôle change de statut, donc la ligne quittera une vue filtrée : le
    // focus tomberait sur `<body>` et l'instruction au clavier repartirait du
    // haut du document, sur l'écran fait précisément pour enchaîner les gestes.
    // On le repose sur la puce du filtre courant, le repère le plus proche.
    const ligneVaPartir = statut !== "tous" && vers !== statut;
    setEnVol((vol) => [...vol, feedback.id]);
    try {
      await changerStatut.mutateAsync({ id: feedback.id, status: vers });
      toast.success(`« ${feedback.title} » passe en « ${LIBELLE_STATUT[vers]} ».`);
      if (ligneVaPartir) filtreActif.current?.focus();
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setEnVol((vol) => vol.filter((id) => id !== feedback.id));
    }
  }

  const barre = (
    <BarreDeStatuts
      actif={statut}
      comptes={comptes}
      onFiltrer={setStatut}
      refActif={filtreActif}
    />
  );

  // La modale est rendue **hors** de la cascade d'états, jamais dans la seule
  // branche nominale : instruire depuis elle le dernier signalement d'un filtre
  // vide la liste, et la modale disparaîtrait alors sous les doigts — avant
  // qu'on ait pu promouvoir le signalement en issue ou coller son URL.
  const modale = ouvert && (
    <FeedbackDetailDialog
      feedback={ouvert}
      open
      onOpenChange={(o) => !o && setOuvert(null)}
    />
  );

  if (isLoading) {
    return (
      <div className="space-y-4">
        {barre}
        <Skeleton className="h-40 w-full" />
        {modale}
      </div>
    );
  }
  if (error) {
    return (
      <div className="space-y-4">
        {barre}
        <EmptyState {...messageDeRefus(error, REFUS)} />
        {modale}
      </div>
    );
  }
  if (!data || data.length === 0) {
    // Rien du tout et « rien sous ce filtre » sont deux situations distinctes :
    // la première attend des signalements, la seconde attend un clic. Tant que
    // les décomptes n'ont pas répondu, une vue **filtrée** vide ne prouve rien
    // sur la base — affirmer « aucun retour utilisateur » y serait faux, et
    // définitivement si la requête de comptage échoue.
    const baseVide = statut === "tous" || comptes?.total === 0;
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
            description="Rien à traiter ici."
            // La sortie est offerte plutôt que nommée : désigner « Tous »
            // laisserait à l'administrateur le soin de retrouver la puce.
            action={
              <Button variant="outline" onClick={() => setStatut("tous")}>
                Voir tous les signalements
              </Button>
            }
          />
        )}
        {modale}
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
                {/* Le titre plafonne plus bas sous `sm` : à `max-w-xs` la
                    colonne d'action commençait au-delà du bord d'un téléphone
                    de 360 px, atteignable seulement après un défilement
                    latéral que rien n'annonce. */}
                <TableCell className="max-w-[10rem] truncate sm:max-w-xs">
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
                      // Le titre est borné à 200 caractères côté API et la
                      // cellule voisine le tronque : le relire en entier à
                      // chaque prise de focus n'aiderait personne.
                      aria-label={`Statut de « ${abrege(f.title)} »`}
                      className={cn(
                        "h-7 cursor-pointer rounded-full border-transparent px-2 text-xs font-medium",
                        FOCUS,
                        APLATS[f.status],
                        // `aria-busy` plutôt que `disabled` : un navigateur
                        // retire le focus d'un contrôle désactivé, et le
                        // reprendre coûterait une tabulation depuis le haut du
                        // document à chaque ligne traitée. La ré-entrée est
                        // gardée dans `changer`, pas par l'attribut.
                        enVol.includes(f.id) && "opacity-60",
                      )}
                      value={f.status}
                      aria-busy={enVol.includes(f.id)}
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
      {modale}
    </div>
  );
}
