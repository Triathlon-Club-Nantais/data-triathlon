"use client";
import { Fragment, useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  ChevronDown,
  ChevronRight,
  Loader2,
  Pencil,
  RefreshCw,
  RotateCcw,
  ShieldAlert,
} from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
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
import { CourseSourcesPanel } from "@/components/courses/CourseSourcesPanel";
import { apiClient } from "@/lib/api/client";
import { eventTypeLabel, providerLabel } from "@/lib/constants";
import { describeQualityIssues, QUALITY_ISSUE_LABELS } from "@/lib/quality";
import {
  useAdminCourses,
  useAdminCoursesCount,
  TAILLE_PAGE_ADMIN,
  type FiltresCourses,
} from "@/lib/queries/admin";
import { useSession } from "@/lib/queries/auth";
import { formatDate } from "@/lib/utils/date";
import { useRescrapeStream } from "@/hooks/useRescrapeStream";
import type { CourseBrief } from "@/lib/types";
import { Champ } from "./AdminFilterField";
import { EditCourseDialog } from "./EditCourseDialog";
import { ReliabilityVerdictDialog, type Verdict } from "./ReliabilityVerdictDialog";

const TOUTES = "all";

/**
 * La file de revalidation qualité (#119).
 *
 * **Une vue filtrée du catalogue, pas une seconde liste** : `GET /courses` avec
 * `unreliable=true` pagine, trie par date décroissante et rend déjà
 * `quality_issues`. Une route dédiée aurait dupliqué tout cela pour un préfixe
 * d'URL, et une seconde liste à tenir à jour après chaque verdict.
 *
 * Un composant distinct de `CoursesAdminTable`, en revanche : les colonnes et
 * les gestes ne sont pas les mêmes, et un composant à deux personnalités, c'est
 * une branche par ligne de rendu et un test par branche.
 *
 * **Le filtre par anomalie agit côté client**, sur la page affichée :
 * `quality_issues` est une colonne JSON, et la filtrer en SQL divergerait entre
 * SQLite (dev) et PostgreSQL (prod). Il affine la page, il ne cherche pas
 * au-delà — à rouvrir le jour où la file dépasse durablement une page.
 */
export function QualityQueueTable({
  page: pageDemandee = 1,
  filtres = {},
}: {
  page?: number;
  filtres?: FiltresCourses;
}) {
  const router = useRouter();
  const chemin = usePathname();
  const qc = useQueryClient();
  const page = Math.max(1, Math.trunc(pageDemandee) || 1);

  const requete = { ...filtres, unreliable: true as const };
  const { data, isLoading, error } = useAdminCourses(page, requete);
  const { data: comptage } = useAdminCoursesCount(requete);
  const session = useSession();
  const rescrape = useRescrapeStream();

  // Client, jamais dans l'URL (voir la doc du composant) : ne rejoint donc pas
  // le brouillon de `FiltresFile`.
  const [anomalie, setAnomalie] = useState("");
  const [aTrancher, setATrancher] = useState<{ course: CourseBrief; verdict: Verdict } | null>(
    null,
  );
  const [aCorriger, setACorriger] = useState<CourseBrief | null>(null);
  // La ligne dont le re-scrape est en cours — posé au clic, remis à `null`
  // juste après l'attente du flux (l'effet ci-dessous s'occupe déjà du toast :
  // lui ajouter cette écriture le ferait poser un état, ce que
  // `react-hooks/set-state-in-effect` refuse). `rescrape.start` n'a rien à
  // faire ici de son côté : c'est bien la ligne qui vient de cliquer qui doit
  // se réinitialiser, pas un effet global qui ne sait pas laquelle a cliqué.
  const [enCoursId, setEnCoursId] = useState<number | null>(null);
  // Les sources dépliées (#739) — un `Set` et non un `number | null` : rien
  // n'empêche de comparer les sources de deux épreuves à la fois.
  const [sourcesOuvertes, setSourcesOuvertes] = useState<Set<number>>(new Set());

  function basculerSources(courseId: number) {
    setSourcesOuvertes((actuelles) => {
      const suivantes = new Set(actuelles);
      if (suivantes.has(courseId)) {
        suivantes.delete(courseId);
      } else {
        suivantes.add(courseId);
      }
      return suivantes;
    });
  }

  async function lancerRescrape(course: CourseBrief) {
    setEnCoursId(course.id);
    await rescrape.start(course.id);
    setEnCoursId(null);
  }

  // Le serveur reste seul juge : ces tests n'autorisent rien, ils évitent de
  // proposer un bouton qui rendrait 403.
  const pouvoirs = session.data?.permissions ?? [];
  const peutTrancher = pouvoirs.includes("quality:override");
  const peutCorriger = pouvoirs.includes("courses:write");
  const peutRescraper = pouvoirs.includes("courses:sources");

  const lignes = data ?? [];
  const affichees = anomalie
    ? lignes.filter((c) => Boolean(c.quality_issues?.[anomalie]))
    : lignes;

  // Les codes proposés sont ceux réellement présents sur la page : une liste
  // figée offrirait des filtres qui ne rendent jamais rien.
  const codes = [...new Set(lignes.flatMap((c) => Object.keys(c.quality_issues ?? {})))];

  // Le nom de l'épreuve en cours de re-scrape, pour l'annonce d'état (AC9) —
  // `enCoursId` seul ne dit rien à un lecteur d'écran.
  const courseEnCours = enCoursId !== null ? lignes.find((c) => c.id === enCoursId) : undefined;

  const total = comptage?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / TAILLE_PAGE_ADMIN));

  function naviguer(valeurs: FiltresCourses, versLaPage: number) {
    const qs = new URLSearchParams();
    Object.entries(valeurs).forEach(([cle, valeur]) => valeur && qs.set(cle, String(valeur)));
    if (versLaPage > 1) qs.set("page", String(versLaPage));
    router.push(qs.size ? `${chemin}?${qs}` : chemin);
  }

  // Notifie en fin de flux plutôt qu'après l'`await` : `start()` ne rejette
  // **jamais** — le hook capture ses propres erreurs dans `state.error` — donc
  // un `try/catch` autour de lui annoncerait un succès sur un échec. Même
  // patron que `CourseSourcesPanel`, pour la même raison.
  useEffect(() => {
    if (rescrape.state.phase === "done") {
      toast.success("Re-scrape terminé — l'indice de fiabilité a été recalculé.");
      // Le serveur vient de réécrire `is_reliable_computed` et
      // `quality_issues` : sans cette invalidation, la ligne reste dans la
      // file avec ses anciennes anomalies malgré le message.
      qc.invalidateQueries({ queryKey: ["admin-courses"] });
    } else if (rescrape.state.phase === "error" && rescrape.state.error) {
      toast.error(rescrape.state.error);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rescrape.state.phase]);

  // La barre de filtres reste montée dans **tous** les états : la retirer sur
  // une file vide enfermerait le validateur dans son propre filtre.
  // `key` resynchronise la saisie brouillon sur l'URL : sans elle, un Retour
  // navigateur laisserait les champs remplis au-dessus d'une liste qui montre
  // autre chose (même patron que `CoursesAdminTable`).
  const barre = (
    <FiltresFile
      key={JSON.stringify(filtres)}
      valeurs={filtres}
      onFiltrer={(v) => naviguer(v, 1)}
      codes={codes}
      anomalie={anomalie}
      onAnomalieChange={setAnomalie}
    />
  );

  // Un `?name=` ou une plage de dates sans correspondance vide la file tout
  // en laissant d'autres épreuves douteuses ailleurs : ce n'est pas la même
  // annonce qu'une file réellement vide (même distinction que
  // `CoursesAdminTable.filtresActifs`).
  const filtresActifs = Object.values(filtres).some(Boolean);

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
          title="File indisponible"
          description={
            error instanceof Error
              ? error.message
              : "La file de revalidation n'a pas pu être chargée. Réessayez plus tard."
          }
        />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {barre}

      {lignes.length === 0 ? (
        filtresActifs ? (
          <EmptyState
            title="Aucun résultat"
            description="Aucune épreuve à revalider ne correspond à ces filtres. Élargissez la recherche."
          />
        ) : (
          <EmptyState
            title="Aucune épreuve à revalider"
            description="Toutes les épreuves du catalogue passent l'indice de fiabilité, ou ont été tranchées à la main."
          />
        )
      ) : (
        <>
          {affichees.length === 0 ? (
            // Le filtre d'anomalie n'agit que sur la page affichée (limite
            // assumée, voir la doc du composant) : il peut vider une page tout
            // en laissant du monde ailleurs — distinct de la file réellement
            // vide. La pagination reste donc hors de ce ternaire (ci-dessous) :
            // sans elle, cet état serait une impasse dès que la file dépasse
            // une page — le seul moyen d'en sortir serait de relâcher le filtre.
            <EmptyState
              title="Aucune épreuve ne porte cette anomalie sur cette page"
              description="Le filtre ne s'applique qu'à la page affichée. Changez de page ou choisissez une autre anomalie."
            />
          ) : (
            <Card className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-11">
                      <span className="sr-only">Sources</span>
                    </TableHead>
                    <TableHead>Épreuve</TableHead>
                    <TableHead>Date</TableHead>
                    <TableHead>Anomalies</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {affichees.map((course) => {
                    const ouverte = sourcesOuvertes.has(course.id);
                    return (
                    <Fragment key={course.id}>
                    <TableRow>
                      <TableCell>
                        <Button
                          size="icon-sm"
                          variant="ghost"
                          className="min-h-11 min-w-11"
                          aria-expanded={ouverte}
                          aria-label={
                            ouverte
                              ? `Masquer les sources — ${course.name}`
                              : `Afficher les sources — ${course.name}`
                          }
                          onClick={() => basculerSources(course.id)}
                        >
                          {ouverte ? (
                            <ChevronDown size={14} aria-hidden="true" />
                          ) : (
                            <ChevronRight size={14} aria-hidden="true" />
                          )}
                        </Button>
                      </TableCell>
                      <TableCell className="whitespace-normal">
                        {/* Vers la page publique de l'épreuve — aucune page
                            `/admin/courses/[id]` dédiée n'existe, et n'a pas
                            à exister (#719) : même route que le lien « Voir la
                            page publique » de `CoursesAdminTable`. */}
                        <Link
                          href={`/courses/${course.id}`}
                          className="font-medium text-primary hover:underline"
                        >
                          {course.name}
                        </Link>
                        <div className="text-xs text-muted-foreground">
                          {eventTypeLabel(course.event_type)} · {providerLabel(course.provider)}
                        </div>
                      </TableCell>
                      <TableCell>{formatDate(course.event_date)}</TableCell>
                      <TableCell className="whitespace-normal">
                        <ul className="space-y-1 text-sm">
                          {describeQualityIssues(course.quality_issues).map((phrase) => (
                            <li key={phrase}>{phrase}</li>
                          ))}
                        </ul>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex flex-wrap justify-end gap-1.5">
                          {peutTrancher && (
                            <>
                              {/* Seul le geste courant reste en toutes lettres — les
                                  deux autres, plus rares, passent en boutons-icône
                                  sur le patron de `CoursesAdminTable` : sans quoi
                                  la colonne Actions dépasse la ligne (constat 2). */}
                              <Button
                                size="sm"
                                className="min-h-11"
                                onClick={() => setATrancher({ course, verdict: "fiable" })}
                              >
                                Marquer fiable
                              </Button>
                              <Button
                                size="icon-sm"
                                variant="outline"
                                className="min-h-11 min-w-11"
                                title="Marquer douteuse"
                                aria-label={`Marquer douteuse — ${course.name}`}
                                onClick={() => setATrancher({ course, verdict: "douteuse" })}
                              >
                                <ShieldAlert />
                              </Button>
                              <Button
                                size="icon-sm"
                                variant="ghost"
                                className="min-h-11 min-w-11"
                                title="Revenir à l'avis calculé"
                                aria-label={`Revenir à l'avis calculé — ${course.name}`}
                                onClick={() => setATrancher({ course, verdict: "calcule" })}
                              >
                                <RotateCcw />
                              </Button>
                            </>
                          )}
                          {peutRescraper && (() => {
                            const active = enCoursId === course.id && rescrape.state.running;
                            return (
                              <Button
                                size="icon-sm"
                                variant="outline"
                                className="min-h-11 min-w-11"
                                // Le hook n'expose qu'un état unique (`activeRef`) : un
                                // second appel concurrent serait silencieusement
                                // ignoré plutôt que traité en parallèle. Toutes les
                                // lignes restent donc désactivées pendant un
                                // re-scrape — seule la ligne active se distingue par
                                // sa progression, ce qui répond au constat sans
                                // prétendre à un re-scrape multi-lignes que le hook
                                // ne porte pas (réserve documentée dans le rapport).
                                disabled={rescrape.state.running}
                                onClick={() => lancerRescrape(course)}
                                title={active ? "Re-scrape en cours" : "Re-scraper l'épreuve"}
                                aria-label={
                                  active
                                    ? `Re-scrape en cours — ${course.name}${
                                        rescrape.state.total > 0
                                          ? ` (${rescrape.state.progress} sur ${rescrape.state.total})`
                                          : ""
                                      }`
                                    : `Re-scraper ${course.name}`
                                }
                              >
                                {active ? (
                                  <Loader2 size={14} className="animate-spin" aria-hidden="true" />
                                ) : (
                                  <RefreshCw size={14} aria-hidden="true" />
                                )}
                              </Button>
                            );
                          })()}
                          {peutCorriger && (
                            <Button
                              size="icon-sm"
                              variant="outline"
                              className="min-h-11 min-w-11"
                              title="Corriger l'épreuve"
                              aria-label={`Éditer ${course.name}`}
                              onClick={() => setACorriger(course)}
                            >
                              <Pencil size={14} />
                            </Button>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                    {ouverte && (
                      <TableRow>
                        <TableCell colSpan={5} className="bg-muted/30">
                          <SourcesDepliees courseId={course.id} />
                        </TableCell>
                      </TableRow>
                    )}
                    </Fragment>
                    );
                  })}
                </TableBody>
              </Table>
            </Card>
          )}

          {/* Hors du ternaire ci-dessus, à dessein : `affichees` peut être
              vide (filtre d'anomalie qui ne retient rien sur cette page) sans
              que `pages` le soit — le total vient de `comptage`, non affecté
              par ce filtre client. La pagination doit rester atteignable dans
              les deux branches non vides, sous peine d'impasse. */}
          {pages > 1 && (
            <nav
              aria-label="Pagination de la file de revalidation"
              className="flex items-center justify-between gap-3 rounded-xl border p-3 text-sm"
            >
              <span aria-current="page">
                Page {page} sur {pages} — {total} épreuve{total > 1 ? "s" : ""} à revalider
              </span>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  className="min-h-11"
                  disabled={page <= 1}
                  onClick={() => naviguer(filtres, page - 1)}
                >
                  ‹ Précédent
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="min-h-11"
                  disabled={page >= pages}
                  onClick={() => naviguer(filtres, page + 1)}
                >
                  Suivant ›
                </Button>
              </div>
            </nav>
          )}
        </>
      )}

      {/* Région live, montée en permanence : un `<p role="status">` inséré
          déjà rempli n'est pas annoncé par plusieurs lecteurs d'écran (seules
          ses mises à jour ultérieures le seraient). Vide au repos, elle
          reçoit son texte au démarrage du flux. Le seul signal visuel restait
          sinon un `Loader2` de 14 px et un `aria-label` porté par un bouton
          non focalisé, jamais ré-annoncé (constat 9). Explique aussi pourquoi
          les autres lignes sont désactivées le temps du flux. */}
      <p role="status" className="text-sm text-[var(--tcn-text-faint)]">
        {rescrape.state.running && courseEnCours
          ? `Re-scrape de ${courseEnCours.name}${
              rescrape.state.total > 0
                ? ` — ${rescrape.state.progress} sur ${rescrape.state.total} résultats`
                : " en cours"
            }. Les autres épreuves de la file sont désactivées le temps du flux.`
          : ""}
      </p>

      {aTrancher && (
        <ReliabilityVerdictDialog
          course={aTrancher.course}
          verdict={aTrancher.verdict}
          onOpenChange={(ouvert) => !ouvert && setATrancher(null)}
        />
      )}
      {aCorriger && (
        <EditCourseDialog
          course={aCorriger}
          open
          onOpenChange={(ouvert) => !ouvert && setACorriger(null)}
        />
      )}
    </div>
  );
}

/**
 * Les sources d'une épreuve, chargées à la demande dans la ligne dépliée
 * (#739). `CourseSourcesPanel` porte déjà l'affichage, la bascule, le
 * re-scrape et la suppression — le réutiliser tel quel évite une seconde
 * liste de sources à tenir dans le back-office.
 */
function SourcesDepliees({ courseId }: { courseId: number }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["course-sources", courseId],
    queryFn: () => apiClient.getCourseSources(courseId),
  });

  if (isLoading) return <Skeleton className="h-8 w-48" />;
  if (error) {
    return (
      <p className="text-sm text-destructive">
        Les sources n&apos;ont pas pu être chargées.
      </p>
    );
  }
  if (!data || data.length === 0) {
    return <p className="text-sm text-muted-foreground">Aucune source enregistrée.</p>;
  }
  return <CourseSourcesPanel courseId={courseId} initialSources={data} />;
}

/**
 * Barre de filtres de la file de revalidation (#119, constat 7 et 11).
 *
 * Même patron que `CatalogueFilters` (`CoursesAdminTable`) pour les trois
 * champs qui écrivent l'URL — saisie brouillon, appliqués au clic ou à
 * `Entrée`, `Réinitialiser` conditionné à un filtre actif — mais un champ de
 * plus, lui **immédiat** : l'anomalie agit côté client sur la page affichée
 * (voir la doc de `QualityQueueTable`), elle n'écrit jamais dans l'URL, donc
 * son état ne rejoint pas le brouillon. Champs non partagés avec le
 * catalogue (pas de discipline ici, une anomalie à la place) : un composant
 * séparé plutôt qu'une duplication forcée de `CatalogueFilters`.
 */
function FiltresFile({
  valeurs,
  onFiltrer,
  codes,
  anomalie,
  onAnomalieChange,
}: {
  valeurs: FiltresCourses;
  onFiltrer: (valeurs: FiltresCourses) => void;
  codes: string[];
  anomalie: string;
  onAnomalieChange: (code: string) => void;
}) {
  const [nom, setNom] = useState(valeurs.name ?? "");
  const [du, setDu] = useState(valeurs.date_from ?? "");
  const [au, setAu] = useState(valeurs.date_to ?? "");

  const actifs = Object.values(valeurs).some(Boolean);

  function appliquer() {
    onFiltrer({ name: nom, date_from: du, date_to: au });
  }

  function reinitialiser() {
    setNom("");
    setDu("");
    setAu("");
    onFiltrer({});
  }

  return (
    <Card>
      <CardContent className="flex flex-wrap items-end gap-3">
        <Champ label="Nom de l'épreuve" htmlFor="filtre-nom">
          <Input
            id="filtre-nom"
            value={nom}
            onChange={(e) => setNom(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && appliquer()}
            placeholder="Rechercher une épreuve"
            className="w-full sm:w-56"
          />
        </Champ>
        <Champ label="Du" htmlFor="filtre-date-debut">
          <Input
            id="filtre-date-debut"
            type="date"
            value={du}
            onChange={(e) => setDu(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && appliquer()}
            className="w-full sm:w-40"
          />
        </Champ>
        <Champ label="Au" htmlFor="filtre-date-fin">
          <Input
            id="filtre-date-fin"
            type="date"
            value={au}
            onChange={(e) => setAu(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && appliquer()}
            className="w-full sm:w-40"
          />
        </Champ>
        {/* Immédiat, pas de brouillon (voir la doc du composant). Le code
            sélectionné reste dans la liste même s'il a disparu de la page
            affichée (changement de page, re-scrape) : sans ça, un `Select`
            contrôlé sur une valeur absente de ses options se réinitialise de
            lui-même, et le filtre se relâcherait en silence plutôt que de
            montrer « aucune épreuve ne porte cette anomalie sur cette page ». */}
        <Champ label="Anomalie" htmlFor="filtre-anomalie">
          <Select
            value={anomalie || TOUTES}
            onValueChange={(v) => onAnomalieChange(v === TOUTES ? "" : (v as string))}
          >
            <SelectTrigger id="filtre-anomalie" className="h-9 w-full sm:w-48">
              <SelectValue placeholder="Toutes">
                {(v) => (!v || v === TOUTES ? "Toutes" : (QUALITY_ISSUE_LABELS[v as string] ?? v))}
              </SelectValue>
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={TOUTES}>Toutes</SelectItem>
              {(anomalie && !codes.includes(anomalie) ? [...codes, anomalie] : codes).map(
                (code) => (
                  <SelectItem key={code} value={code}>
                    {QUALITY_ISSUE_LABELS[code] ?? code}
                  </SelectItem>
                ),
              )}
            </SelectContent>
          </Select>
        </Champ>
        <div className="flex gap-2">
          <Button className="min-h-11" onClick={appliquer}>
            Filtrer
          </Button>
          {actifs && (
            <Button variant="ghost" className="min-h-11" onClick={reinitialiser}>
              Réinitialiser
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
