import { Card, FormatChip, LigneCarte } from "@/components/tcn";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { eventTypeLabel } from "@/lib/constants";
import type { Gender } from "@/lib/scope";
import type { ClubBestTime } from "@/lib/types";
import { formatDate } from "@/lib/utils/date";
import { disciplineOf, formatToken } from "@/lib/utils/format";

const GENDER_LABELS: Record<string, string> = { F: "Femmes", M: "Hommes" };

/**
 * Meilleur temps du club par discipline, format calibré et genre (#1588),
 * calculé côté serveur (`GET /club/best-times`). Un meilleur temps, jamais un
 * record : deux M n'ont pas forcément le même parcours (#1361).
 */
export function ClubBestTimesCard({
  seasonLines,
  allLines,
  seasonLabel,
  gender,
}: {
  seasonLines: ClubBestTime[];
  allLines: ClubBestTime[];
  seasonLabel: string;
  gender?: Gender;
}) {
  // `/club/best-times` renvoie une ligne par genre : le filtre se fait ici.
  if (gender) {
    seasonLines = seasonLines.filter((l) => l.gender === gender);
    allLines = allLines.filter((l) => l.gender === gender);
  }
  if (allLines.length === 0 && seasonLines.length === 0) return null;

  return (
    <Card padding={0} style={{ overflow: "hidden" }}>
      <div style={{ padding: "20px 26px 12px" }}>
        <h2
          style={{
            fontFamily: "var(--tcn-font-display)",
            fontSize: 22,
            fontWeight: 400,
            color: "var(--tcn-ink)",
            margin: 0,
          }}
        >
          Meilleurs temps du club
        </h2>
        <p style={{ margin: "6px 0 0", fontSize: 13, color: "var(--tcn-text-faint)" }}>
          Un temps par discipline, par format et par genre. Deux épreuves d&apos;un même format
          n&apos;ont pas toujours le même parcours.
        </p>
      </div>
      <Tabs defaultValue={seasonLines.length > 0 ? "season" : "all"}>
        <TabsList className="mx-[26px] h-11">
          <TabsTrigger value="season">{seasonLabel}</TabsTrigger>
          <TabsTrigger value="all">Toutes les saisons</TabsTrigger>
        </TabsList>
        <TabsContent value="season">
          {seasonLines.length > 0 ? (
            <Lines lines={seasonLines} />
          ) : (
            // Seul cet onglet peut être vide : la saison est incluse dans toutes les saisons.
            <p style={{ margin: 0, padding: "12px 26px 20px", fontSize: 14, color: "var(--tcn-text-faint)" }}>
              Aucun temps comparable sur cette saison. Les meilleurs temps des saisons
              précédentes sont sous « Toutes les saisons ».
            </p>
          )}
        </TabsContent>
        <TabsContent value="all">
          <Lines lines={allLines} />
        </TabsContent>
      </Tabs>
    </Card>
  );
}

function Lines({ lines }: { lines: ClubBestTime[] }) {
  return lines.map((line) => {
    const format = formatToken(line.event_type);
    return (
      <LigneCarte
        key={`${line.event_type}|${line.gender}`}
        href={`/courses/${line.course_id}/participations/${line.participation_id}`}
        // Le format est déjà dit par le préfixe masqué de la valeur.
        marqueur={
          <span aria-hidden="true">
            <FormatChip>{format}</FormatChip>
          </span>
        }
        titre={`${eventTypeLabel(disciplineOf(line.event_type))}, ${GENDER_LABELS[line.gender] ?? line.gender}`}
        meta={[line.athlete_name, line.event_name, formatDate(line.event_date)].filter(Boolean).join(", ")}
        valeur={
          <>
            <span className="sr-only">meilleur temps sur {format} : </span>
            {line.total_time}
          </>
        }
      />
    );
  });
}
