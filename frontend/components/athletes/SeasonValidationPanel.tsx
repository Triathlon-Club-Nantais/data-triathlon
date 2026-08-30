"use client";
import { toast } from "sonner";
import { Button, Card } from "@/components/tcn";
import {
  useDeclareVolunteerAction,
  useSeasonQuota,
  useUnvalidateSeason,
  useValidateSeason,
} from "@/lib/queries/admin";
import { useSession } from "@/lib/queries/auth";
import { currentSeason } from "@/lib/utils/season";

export type CoureurAValider = {
  id: number;
  nom: string;
  prenom: string;
};

const ECHEC_DECLARATION = "La déclaration n'a pas abouti. Réessayez dans un instant.";
const ECHEC_VALIDATION = "La saison n'a pas pu être validée. Réessayez dans un instant.";
const ECHEC_DEVALIDATION = "La saison n'a pas pu être dévalidée. Réessayez dans un instant.";

/**
 * Actions d'administration du quota de saison d'un coureur (#709) — sur la
 * fiche publique, comme `AthleteAdminPanel`, invisible sans le pouvoir dédié.
 * Deux sections indépendantes : déclarer un bénévolat (US2) et
 * valider/dévalider la saison (US3) — deux pouvoirs distincts (FR-007, FR-009).
 */
export function SeasonValidationPanel({ athlete }: { athlete: CoureurAValider }) {
  const session = useSession();
  const peutDeclarerBenevolat =
    session.data?.permissions.includes("athletes:volunteer_manage") ?? false;
  const peutValiderSaison = session.data?.permissions.includes("athletes:season_validate") ?? false;

  if (!peutDeclarerBenevolat && !peutValiderSaison) return null;

  return (
    <Card>
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {peutDeclarerBenevolat && <DeclarerBenevolat athleteId={athlete.id} />}
        {peutValiderSaison && <ValiderSaison athleteId={athlete.id} />}
      </div>
    </Card>
  );
}

function DeclarerBenevolat({ athleteId }: { athleteId: number }) {
  const declarer = useDeclareVolunteerAction();

  async function handleDeclarer() {
    try {
      await declarer.mutateAsync({ athleteId, season: currentSeason() });
      toast.success("Action de bénévolat déclarée.");
    } catch {
      toast.error(ECHEC_DECLARATION);
    }
  }

  return (
    <Button
      variant="secondary"
      onClick={handleDeclarer}
      disabled={declarer.isPending}
      aria-busy={declarer.isPending}
    >
      Déclarer une action de bénévolat
    </Button>
  );
}

function ValiderSaison({ athleteId }: { athleteId: number }) {
  const season = currentSeason();
  const quota = useSeasonQuota(athleteId, season, true);
  const valider = useValidateSeason();
  const devalider = useUnvalidateSeason();

  if (!quota.data) return null;

  const { validated_count, has_volunteer_action, season_validated } = quota.data;

  async function handleValider() {
    try {
      await valider.mutateAsync({ athleteId, season });
      toast.success("Saison validée.");
    } catch {
      toast.error(ECHEC_VALIDATION);
    }
  }

  async function handleDevalider() {
    try {
      await devalider.mutateAsync({ athleteId, season });
      toast.success("Saison dévalidée.");
    } catch {
      toast.error(ECHEC_DEVALIDATION);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {/* FR-012 — indicatif, ne bloque jamais la validation (FR-011). */}
      <p style={{ fontSize: 12, color: "var(--tcn-text-faint)" }}>
        {validated_count}/3 épreuves validées · bénévolat{" "}
        {has_volunteer_action ? "déclaré" : "non déclaré"}
      </p>
      {season_validated ? (
        <Button
          variant="secondary"
          onClick={handleDevalider}
          disabled={devalider.isPending}
          aria-busy={devalider.isPending}
        >
          Dévalider la saison
        </Button>
      ) : (
        <Button
          variant="secondary"
          onClick={handleValider}
          disabled={valider.isPending}
          aria-busy={valider.isPending}
        >
          Valider la saison
        </Button>
      )}
    </div>
  );
}
