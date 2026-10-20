import Link from "next/link";
import { Card, Eyebrow } from "@/components/tcn";
import { Skeleton } from "@/components/ui/skeleton";
import { useMySeasonQuota } from "@/lib/queries/auth";
import type { SeasonQuota } from "@/lib/types";
import { seasonLabel } from "@/lib/utils/season";

const corps = { margin: "12px 0 0", fontSize: 15 } as const;
const statut = { ...corps, fontWeight: 600 } as const;

function Manque({ quota }: { quota: SeasonQuota }) {
  const { validated_count: n, required_events: requis } = quota;
  return (
    <>
      <p style={corps}>
        {n >= requis
          ? `Épreuves : objectif de ${requis} atteint`
          : `${n} ${n > 1 ? "épreuves comptées" : "épreuve comptée"} sur ${requis} ${requis > 1 ? "requises" : "requise"}`}
      </p>
      <p style={{ ...corps, marginTop: 4 }}>
        Bénévolat : {quota.has_volunteer_action ? "action validée" : quota.has_pending_volunteer_action ? "action en attente de validation" : "aucune action déclarée"}
      </p>
      {!quota.has_volunteer_action && !quota.has_pending_volunteer_action && (
        <Link href="/benevolat" className="tcn-cible-tactile font-semibold text-accent-ink hover:underline" style={{ display: "inline-block", marginTop: 8, fontSize: 14 }}>
          Déclarer une action
        </Link>
      )}
    </>
  );
}

/** Avancement vers la validation de la saison, tel que l'API le dit (#1671). */
export function MaSaisonAuClub() {
  const { data, isPending, isError } = useMySeasonQuota();
  if (!isPending && !isError && data === null) return null;
  return (
    <Card padding={20} aria-busy={isPending || undefined}>
      <Eyebrow role="heading" aria-level={2}>
        Ma saison au club
      </Eyebrow>
      {isPending && <Skeleton style={{ height: 48, marginTop: 12 }} />}
      {isError && (
        <p role="alert" style={corps}>
          Impossible d&rsquo;afficher votre saison pour le moment. Rechargez la page pour réessayer.
        </p>
      )}
      {data && <p style={{ margin: "4px 0 0", fontSize: 13, color: "var(--tcn-text-muted)" }}>{seasonLabel(data.season)}</p>}
      {data &&
        (data.season_validated ? (
          <p style={statut}>Saison validée</p>
        ) : data.quota_met ? (
          <p style={statut}>Conditions remplies, en attente de validation par le club</p>
        ) : (
          <Manque quota={data} />
        ))}
    </Card>
  );
}
