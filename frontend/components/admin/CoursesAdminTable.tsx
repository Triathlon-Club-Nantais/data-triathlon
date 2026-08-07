"use client";
import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ExternalLink, Eye, ListOrdered, Pencil, Trash2 } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { EVENT_TYPE_OPTIONS, eventTypeLabel, providerLabel } from "@/lib/constants";
import {
  useAdminCourses,
  useAdminCoursesCount,
  TAILLE_PAGE_ADMIN,
  type FiltresCourses,
} from "@/lib/queries/admin";
import { useSession } from "@/lib/queries/auth";
import { cn } from "@/lib/utils";
import { formatDate } from "@/lib/utils/date";
import type { CourseBrief } from "@/lib/types";
import { DeleteCourseDialog } from "./DeleteCourseDialog";
import { CourseParticipationsDialog } from "./CourseParticipationsDialog";
import { EditCourseDialog } from "./EditCourseDialog";

/**
 * Le catalogue d'épreuves, côté administration (#117).
 *
 * **Paginé, et ce n'est pas cosmétique** : la base en compte 211 pour une
 * tranche de 20. Sans ces deux boutons, l'essentiel du catalogue serait
 * inatteignable depuis le back-office — donc ni corrigeable ni supprimable,
 * ce qui viderait SC-001 (« sans aucun accès direct à la base ») de son sens.
 * Les filtres tiennent l'autre bout : à 20 par page, atteindre une épreuve
 * précise à la pagination seule demanderait une dizaine de clics.
 *
 * Le nombre de pages et le décompte viennent de `GET /courses/count`, une route
 * à part : `GET /courses` rend une liste, et l'envelopper dans une page pour y
 * loger un `total` serait un changement de contrat de v1 (Principe IV).
 *
 * **L'URL porte l'état de la vue** — page et filtres —, comme la page publique
 * des résultats. C'est ce qui rend une page atteignable directement, partageable
 * entre administrateurs et compatible avec le bouton Retour. Tout dans l'URL ou
 * rien : n'y mettre que la page rendrait au Retour une page 3 non filtrée sous
 * des champs restés remplis. Ce composant l'**écrit** ; c'est la page serveur
 * qui la lit et la lui repasse en props (voir `app/admin/courses/page.tsx`).
 *
 * **Pas de branche 401/403 ici**, contrairement à `PendingProvidersTable` :
 * `GET /courses` est une lecture publique, sans garde. Ces deux états seraient
 * inatteignables, et les tester exigerait de fabriquer une erreur que le serveur
 * ne peut pas produire (Principe VI).
 */
export function CoursesAdminTable({
  page: pageDemandee = 1,
  filtres = {},
}: {
  page?: number;
  filtres?: FiltresCourses;
}) {
  const router = useRouter();
  const chemin = usePathname();

  // `?page=` donne NaN, `?page=-4` un négatif : les deux retombent sur 1 plutôt
  // que de rendre une tranche vide sans rien dire.
  const page = Math.max(1, Math.trunc(pageDemandee) || 1);

  const { data, isLoading, error } = useAdminCourses(page, filtres);
  const { data: comptage } = useAdminCoursesCount(filtres);
  const session = useSession();
  const [aSupprimer, setASupprimer] = useState<CourseBrief | null>(null);
  const [aDetailler, setADetailler] = useState<CourseBrief | null>(null);
  const [aCorriger, setACorriger] = useState<CourseBrief | null>(null);

  // Le serveur reste seul juge (FR-009) : ces tests n'autorisent rien, ils
  // évitent de proposer un bouton qui rendrait 403.
  const peutSupprimer = session.data?.permissions.includes("courses:delete") ?? false;
  const peutCorriger = session.data?.permissions.includes("courses:write") ?? false;

  function naviguer(valeurs: FiltresCourses, versLaPage: number) {
    const qs = new URLSearchParams();
    Object.entries(valeurs).forEach(([cle, valeur]) => valeur && qs.set(cle, valeur));
    // La page 1 ne s'écrit pas : `?page=1` est du bruit dans une URL partagée.
    if (versLaPage > 1) qs.set("page", String(versLaPage));
    router.push(qs.size ? `${chemin}?${qs}` : chemin);
  }

  // Filtrer remet en page 1 : rester en page 4 d'un catalogue qui vient de
  // tomber à trois lignes n'afficherait rien, sans dire pourquoi.
  const filtrer = (valeurs: FiltresCourses) => naviguer(valeurs, 1);
  const allerPage = (versLaPage: number) => naviguer(filtres, versLaPage);

  // La barre de filtres reste montée dans **tous** les états : la retirer sur
  // un résultat vide enfermerait l'administrateur dans son propre filtre.
  const filtresActifs = Object.values(filtres).some(Boolean);
  // La `key` resynchronise la saisie brouillon sur l'URL : sans elle, un Retour
  // navigateur laisserait les champs remplis au-dessus d'une liste non filtrée.
  const barre = (
    <CatalogueFilters key={JSON.stringify(filtres)} valeurs={filtres} onFiltrer={filtrer} />
  );

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
        <EmptyState
          title="Catalogue indisponible"
          description="Les épreuves n'ont pas pu être chargées. Réessayez plus tard."
        />
      </div>
    );
  }
  if (!data || (data.length === 0 && page === 1)) {
    return (
      <div className="space-y-4">
        {barre}
        {filtresActifs ? (
          <EmptyState
            title="Aucun résultat"
            description="Aucune épreuve ne correspond à ces filtres. Élargissez la recherche."
          />
        ) : (
          <EmptyState
            title="Aucune épreuve"
            description="Le catalogue est vide : importez une épreuve depuis son URL de chronométrage."
          />
        )}
      </div>
    );
  }

  // Le total vient de `GET /courses/count`, et il peut manquer un instant — il
  // voyage dans sa propre requête. Sans lui, une tranche incomplète reste le
  // signe qu'on est en dernière page : les boutons restent justes, seul le
  // « sur N » attend. Annoncer un nombre de pages deviné serait pire que rien.
  const total = comptage?.total;
  const nbPages = total === undefined ? undefined : Math.max(1, Math.ceil(total / TAILLE_PAGE_ADMIN));
  const derniereTranche = nbPages === undefined ? data.length < TAILLE_PAGE_ADMIN : page >= nbPages;

  return (
    <div className="space-y-4">
      {barre}
      <Card className="p-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Épreuve</TableHead>
              <TableHead>Date</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Source</TableHead>
              <TableHead></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.map((course) => (
              <TableRow key={course.id}>
                <TableCell className="max-w-xs truncate">{course.name}</TableCell>
                <TableCell>{formatDate(course.event_date)}</TableCell>
                {/* Le slug reste affiché tel quel s'il est inconnu de la table :
                    une administration qui masque « triathlon-xxl » derrière un
                    tiret cache justement l'épreuve à corriger. */}
                <TableCell>{eventTypeLabel(course.event_type)}</TableCell>
                {/* La page de chronométrage d'origine : c'est elle qu'on ouvre
                    pour trancher si une donnée douteuse vient du scraper ou de
                    la source. `rel="noreferrer"` parce que la cible est un
                    domaine tiers, jamais le nôtre. */}
                <TableCell>
                  {course.source_url ? (
                    <a
                      href={course.source_url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 text-primary hover:underline"
                      title={course.source_url}
                    >
                      {providerLabel(course.provider)}
                      <ExternalLink className="size-3.5" />
                    </a>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </TableCell>
                <TableCell className="text-right">
                  {/* Trois pastilles **bordées et colorées au repos** : sans
                      contour un bouton-icône ne se lit pas comme un contrôle,
                      et sans couleur rien ne dit lequel détruit. Le survol
                      ajoute l'aplat. Le libellé porte le nom de l'épreuve,
                      sans quoi la page aligne cinquante « Supprimer »
                      indiscernables à la lecture d'écran ; `title` suffit à
                      l'infobulle, plutôt qu'installer @radix-ui/react-tooltip
                      pour trois boutons. */}
                  <div className="flex justify-end gap-1.5">
                    {/* Un vrai `<Link>` habillé en bouton, et non un `Button`
                        qui se rendrait en lien : celui-ci reste un `<button>`
                        pour Base UI, qui pose alors les sémantiques natives
                        d'un bouton sur une ancre — et `nativeButton={false}`
                        n'arrange rien, il y écrit `role="button"` et efface le
                        rôle de lien. */}
                    <Link
                      href={`/courses/${course.id}`}
                      className={cn(
                        buttonVariants({ variant: "outline", size: "icon-sm" }),
                        "text-muted-foreground hover:bg-muted hover:text-foreground",
                      )}
                      title="Voir la page publique"
                      aria-label={`Page publique — ${course.name}`}
                    >
                      <Eye />
                    </Link>
                    <Button
                      size="icon-sm"
                      variant="outline"
                      className="text-muted-foreground hover:bg-muted hover:text-foreground"
                      title="Voir les résultats"
                      aria-label={`Résultats — ${course.name}`}
                      onClick={() => setADetailler(course)}
                    >
                      <ListOrdered />
                    </Button>
                    {peutCorriger && (
                      <Button
                        size="icon-sm"
                        variant="outline"
                        className="border-primary/25 text-primary hover:border-primary/50 hover:bg-primary/10 hover:text-primary"
                        title="Corriger l'épreuve"
                        aria-label={`Corriger — ${course.name}`}
                        onClick={() => setACorriger(course)}
                      >
                        <Pencil />
                      </Button>
                    )}
                    {peutSupprimer && (
                      <Button
                        size="icon-sm"
                        variant="outline"
                        className="border-destructive/25 text-destructive hover:border-destructive/50 hover:bg-destructive/10 hover:text-destructive"
                        title="Supprimer l'épreuve"
                        aria-label={`Supprimer — ${course.name}`}
                        onClick={() => setASupprimer(course)}
                      >
                        <Trash2 />
                      </Button>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>

        {/* Dans la carte, comme au classement d'une épreuve : la navigation
            appartient au tableau qu'elle feuillette, pas à la page. */}
        <nav
          aria-label="Pagination du catalogue"
          className="flex items-center justify-center gap-3 border-t p-3"
        >
          <Button
            variant="outline"
            size="sm"
            disabled={page === 1}
            onClick={() => allerPage(page - 1)}
          >
            ‹ Précédent
          </Button>
          <span className="text-muted-foreground text-sm" aria-current="page">
            {nbPages === undefined ? `Page ${page}` : `Page ${page} sur ${nbPages}`}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={derniereTranche}
            onClick={() => allerPage(page + 1)}
          >
            Suivant ›
          </Button>
        </nav>

        {total !== undefined && (
          <div className="text-muted-foreground border-t p-3 text-center text-sm">
            {resume(total, filtresActifs)}
          </div>
        )}
      </Card>

      {aSupprimer && (
        <DeleteCourseDialog
          course={aSupprimer}
          open
          onOpenChange={(ouvert) => !ouvert && setASupprimer(null)}
        />
      )}

      {aCorriger && (
        <EditCourseDialog
          course={aCorriger}
          open
          onOpenChange={(ouvert) => !ouvert && setACorriger(null)}
        />
      )}

      {aDetailler && (
        <CourseParticipationsDialog
          course={aDetailler}
          open
          onOpenChange={(ouvert) => !ouvert && setADetailler(null)}
        />
      )}
    </div>
  );
}

/** « 211 épreuves au catalogue », « 1 épreuve correspond aux filtres ». */
function resume(total: number, filtre: boolean): string {
  const pluriel = total > 1 ? "s" : "";
  if (!filtre) return `${total} épreuve${pluriel} au catalogue`;
  return `${total} épreuve${pluriel} ${total > 1 ? "correspondent" : "correspond"} aux filtres`;
}

const TOUTES = "all";

/**
 * Les filtres du catalogue, calqués sur ceux de la page publique des résultats.
 *
 * L'état vit ici, pas dans l'URL — contrairement à `ResultsFilters` : cet écran
 * est un client component sous une garde de session, et un back-office ne se
 * partage pas par lien. Une saisie brouillon, appliquée au clic ou à `Entrée` :
 * filtrer à chaque frappe déclencherait une requête par lettre.
 */
function CatalogueFilters({
  valeurs,
  onFiltrer,
}: {
  valeurs: FiltresCourses;
  onFiltrer: (valeurs: FiltresCourses) => void;
}) {
  const [nom, setNom] = useState(valeurs.name ?? "");
  const [type, setType] = useState(valeurs.event_type ?? "");
  const [du, setDu] = useState(valeurs.date_from ?? "");
  const [au, setAu] = useState(valeurs.date_to ?? "");

  const actifs = Object.values(valeurs).some(Boolean);

  function appliquer() {
    onFiltrer({ name: nom, event_type: type, date_from: du, date_to: au });
  }

  function reinitialiser() {
    setNom("");
    setType("");
    setDu("");
    setAu("");
    onFiltrer({});
  }

  return (
    <Card>
      <CardContent className="flex flex-wrap items-end gap-3">
        <Champ label="Épreuve">
          <Input
            value={nom}
            onChange={(e) => setNom(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && appliquer()}
            placeholder="Rechercher une épreuve"
            className="w-full sm:w-56"
          />
        </Champ>
        <Champ label="Discipline">
          <Select
            value={type || TOUTES}
            onValueChange={(v) => setType(v === TOUTES ? "" : (v as string))}
          >
            <SelectTrigger className="h-9 w-full sm:w-48">
              <SelectValue placeholder="Toutes les disciplines">
                {(v) =>
                  !v || v === TOUTES ? "Toutes les disciplines" : eventTypeLabel(v as string)
                }
              </SelectValue>
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={TOUTES}>Toutes les disciplines</SelectItem>
              {EVENT_TYPE_OPTIONS.map((o) => (
                <SelectItem key={o.value} value={o.value}>
                  {o.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Champ>
        <Champ label="Du">
          <Input
            type="date"
            value={du}
            onChange={(e) => setDu(e.target.value)}
            className="w-full sm:w-40"
          />
        </Champ>
        <Champ label="Au">
          <Input
            type="date"
            value={au}
            onChange={(e) => setAu(e.target.value)}
            className="w-full sm:w-40"
          />
        </Champ>
        <div className="flex gap-2">
          <Button onClick={appliquer}>Filtrer</Button>
          {actifs && (
            <Button variant="ghost" onClick={reinitialiser}>
              Réinitialiser
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function Champ({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex w-full flex-col gap-1.5 sm:w-auto">
      <label className="text-xs font-medium text-muted-foreground">{label}</label>
      {children}
    </div>
  );
}
