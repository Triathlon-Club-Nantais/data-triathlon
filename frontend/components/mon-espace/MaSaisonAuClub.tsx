import Link from "next/link";
import { Card, Eyebrow } from "@/components/tcn";
import { Skeleton } from "@/components/ui/skeleton";
import { useMySeasonQuota } from "@/lib/queries/auth";
import type { SeasonQuota } from "@/lib/types";
import { seasonLabel } from "@/lib/utils/season";

const corps = { margin: "12px 0 0", fontSize: 15 } as const;

function Manque({ quota }: { quota: SeasonQuota }) {
  const { validated_count: n, required_events: requis } = quota;
  return (
    <>
      <p style={corps}>
        {n} {n > 1 ? "épreuves comptées" : "épreuve comptée"} sur {requis} {requis > 1 ? "requises" : "requise"}
      </p>
      <p style={{ ...corps, marginTop: 4 }}>
        Bénévolat : {quota.has_volunteer_action ? "action validée" : quota.has_pending_volunteer_action ? "action en attente de validation" : "aucune action déclarée"}
      </p>
      {!quota.has_volunteer_action && !quota.has_pending_volunteer_action && (
        <Link href="/benevolat" className="text-sm underline underline-offset-2" style={{ display: "inline-block", marginTop: 8 }}>
          Déclarer une action
        </Link>
      )}
    </>
  );
}

/** Avancement vers la validation de la saison, tel que l'API le dit (#1671). */
export function MaSaisonAuClub() {
  const { data, isPending, isError } = useMySeasonQuota(true);
  if (!isPending && !isError && data === null) return null;
  return (
    <Card padding={20}>
      <Eyebrow role="heading" aria-level={2}>
        {data ? `Ma saison au club, ${seasonLabel(data.season)}` : "Ma saison au club"}
      </Eyebrow>
      {isPending && <Skeleton style={{ height: 20, marginTop: 12 }} />}
      {isError && <p style={corps}>Impossible d&rsquo;afficher votre saison pour le moment.</p>}
      {data &&
        (data.season_validated ? (
          <p style={corps}>Saison validée</p>
        ) : data.quota_met ? (
          <p style={corps}>Conditions remplies, en attente de validation par le club</p>
        ) : (
          <Manque quota={data} />
        ))}
    </Card>
  );
}
