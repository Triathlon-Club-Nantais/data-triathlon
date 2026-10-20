import { Card, Eyebrow } from "@/components/tcn";
import { useClubRosterRank } from "@/lib/queries/club";
import { ordinalFr } from "@/lib/utils/format";

function evolution(avant: number, apres: number): string {
  const places = avant - apres;
  if (places === 0) return "Même place que la saison précédente";
  return `${Math.abs(places)} ${Math.abs(places) > 1 ? "places" : "place"} ${places > 0 ? "gagnées" : "perdues"} depuis la saison précédente`;
}

/** Rang parmi les athlètes actifs du club sur la sélection, masqué sans rang (#1700). */
export function MaPlaceAuClub({ athleteId, seasons, federalOnly }: { athleteId: number; seasons: number[]; federalOnly: boolean }) {
  const rang = useClubRosterRank(athleteId, { federalOnly, seasons, enabled: true });
  // Écart seulement sur une saison, comme « Mes chiffres ».
  const unique = seasons.length === 1;
  const avant = useClubRosterRank(athleteId, { federalOnly, seasons: unique ? [seasons[0] - 1] : [], enabled: unique });

  if (!rang.data) return null;
  return (
    <Card padding={20}>
      <Eyebrow>Ma place au club</Eyebrow>
      <p style={{ margin: "12px 0 0", fontFamily: "var(--tcn-font-display)", fontSize: 26, color: "var(--tcn-ink)" }}>
        {`${ordinalFr(rang.data.rank)} sur ${rang.data.total}`}
      </p>
      {avant.data && <p style={{ margin: "4px 0 0", fontSize: 13, color: "var(--tcn-text-muted)" }}>{evolution(avant.data.rank, rang.data.rank)}</p>}
    </Card>
  );
}
