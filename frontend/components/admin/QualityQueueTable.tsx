"use client";
import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Loader2, Pencil, RefreshCw } from "lucide-react";
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
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
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
import { EditCourseDialog } from "./EditCourseDialog";
import { ReliabilityVerdictDialog, type Verdict } from "./ReliabilityVerdictDialog";

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
    <Card key={JSON.stringify(filtres)}>
      <CardContent className="flex flex-wrap items-end gap-3 pt-6">
        <div className="space-y-1">
          <label className="text-sm" htmlFor="filtre-nom">
            Nom de l&apos;épreuve
          </label>
          <Input
            id="filtre-nom"
            defaultValue={filtres.name ?? ""}
            onBlur={(e) => naviguer({ ...filtres, name: e.target.value || undefined }, 1)}
          />
        </div>
        <div className="space-y-1">
          <label className="text-sm" htmlFor="filtre-date-debut">
            Du
          </label>
          <Input
            id="filtre-date-debut"
            type="date"
            defaultValue={filtres.date_from ?? ""}
            onBlur={(e) => naviguer({ ...filtres, date_from: e.target.value || undefined }, 1)}
          />
        </div>
        <div className="space-y-1">
          <label className="text-sm" htmlFor="filtre-date-fin">
            Au
          </label>
          <Input
            id="filtre-date-fin"
            type="date"
            defaultValue={filtres.date_to ?? ""}
            onBlur={(e) => naviguer({ ...filtres, date_to: e.target.value || undefined }, 1)}
          />
        </div>
        <div className="space-y-1">
          <label className="text-sm" htmlFor="filtre-anomalie">
            Anomalie
          </label>
          <select
            id="filtre-anomalie"
            className="h-9 rounded-md border px-3 text-sm"
            value={anomalie}
            onChange={(e) => setAnomalie(e.target.value)}
          >
            <option value="">Toutes</option>
            {codes.map((code) => (
              <option key={code} value={code}>
                {QUALITY_ISSUE_LABELS[code] ?? code}
              </option>
            ))}
          </select>
        </div>
      </CardContent>
    </Card>
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
        <EmptyState title="La file n'a pas pu être chargée." description={String(error)} />
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
      ) : affichees.length === 0 ? (
        // Le filtre d'anomalie n'agit que sur la page affichée (limite
        // assumée, voir la doc du composant) : il peut vider une page tout en
        // laissant du monde ailleurs — distinct de la file réellement vide.
        <EmptyState
          title="Aucune épreuve ne porte cette anomalie sur cette page"
          description="Le filtre ne s'applique qu'à la page affichée. Changez de page ou choisissez une autre anomalie."
        />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Épreuve</TableHead>
              <TableHead>Date</TableHead>
              <TableHead>Anomalies</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {affichees.map((course) => (
              <TableRow key={course.id}>
                <TableCell>
                  <div className="font-medium">{course.name}</div>
                  <div className="text-xs text-muted-foreground">
                    {eventTypeLabel(course.event_type)} · {providerLabel(course.provider)}
                  </div>
                </TableCell>
                <TableCell>{formatDate(course.event_date)}</TableCell>
                <TableCell>
                  <ul className="space-y-1 text-sm">
                    {describeQualityIssues(course.quality_issues).map((phrase) => (
                      <li key={phrase}>{phrase}</li>
                    ))}
                  </ul>
                </TableCell>
                <TableCell className="space-x-2 text-right">
                  {peutTrancher && (
                    <>
                      <Button
                        size="sm"
                        onClick={() => setATrancher({ course, verdict: "fiable" })}
                      >
                        Marquer OK
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setATrancher({ course, verdict: "douteuse" })}
                      >
                        Marquer douteuse
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => setATrancher({ course, verdict: "calcule" })}
                      >
                        Revenir à l&apos;avis calculé
                      </Button>
                    </>
                  )}
                  {peutRescraper && (() => {
                    const active = enCoursId === course.id && rescrape.state.running;
                    return (
                      <Button
                        size="sm"
                        variant="outline"
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
                      size="sm"
                      variant="outline"
                      onClick={() => setACorriger(course)}
                      aria-label={`Éditer ${course.name}`}
                    >
                      <Pencil size={14} />
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      {pages > 1 && (
        <div className="flex items-center justify-between text-sm">
          <span>
            Page {page} sur {pages} — {total} épreuve{total > 1 ? "s" : ""} à revalider
          </span>
          <div className="space-x-2">
            <Button
              size="sm"
              variant="outline"
              disabled={page <= 1}
              onClick={() => naviguer(filtres, page - 1)}
            >
              Précédente
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={page >= pages}
              onClick={() => naviguer(filtres, page + 1)}
            >
              Suivante
            </Button>
          </div>
        </div>
      )}

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
