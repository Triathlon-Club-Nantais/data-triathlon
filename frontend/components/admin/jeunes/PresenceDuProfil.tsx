import { Card } from "@/components/ui/card";
import type { ProfileAttendance } from "@/lib/types";
import { motCompte, pctFr, tauxAssiduite } from "@/lib/utils/format";

/** Assiduité de la saison FFTri en cours (#1364). */
export function PresenceDuProfil({ attendance }: { attendance: ProfileAttendance }) {
  const { attended, pointed, absence_streak } = attendance;
  const taux = tauxAssiduite(attended, pointed);
  return (
    <Card className="space-y-2 p-4">
      <div className="text-lg font-bold">Présence</div>
      <p className="text-[var(--tcn-text-faint)] text-sm">
        Saison FFTri en cours. Seules les séances pointées comptent.
      </p>
      {taux === null ? (
        <p>Aucun appel cette saison.</p>
      ) : (
        <p>{`Assiduité : ${pctFr(taux, 0)} (${motCompte(attended, "séance")} sur ${pointed})`}</p>
      )}
      {absence_streak === 1 && <p>Dernière séance manquée.</p>}
      {absence_streak >= 2 && <p>{absence_streak} séances manquées d&apos;affilée.</p>}
    </Card>
  );
}
