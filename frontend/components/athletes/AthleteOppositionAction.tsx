"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Alert, Button, Input, Modal } from "@/components/tcn";
import { apiClient } from "@/lib/api/client";
import { useApplyOpposition } from "@/lib/queries/admin";
import { useHydratedSession } from "@/lib/queries/auth";
import type { OppositionPreview } from "@/lib/types";
import { localToday } from "@/lib/utils/date";
import type { CoureurACorriger } from "./AthleteAdminPanel";

const ECHEC = "L'opposition n'a pas pu être appliquée. Réessayez dans un instant.";

/**
 * Droit d'opposition (#334), depuis la fiche de l'athlète, sous `oppositions:manage`.
 * Geste définitif : la confirmation chiffre les résultats touchés, homonymes compris,
 * et la fiche disparaît ensuite, d'où le retour à la liste des résultats.
 */
export function AthleteOppositionAction({ athlete }: { athlete: CoureurACorriger }) {
  const session = useHydratedSession();
  const router = useRouter();
  const appliquer = useApplyOpposition();
  const [ouverte, setOuverte] = useState(false);
  const [apercu, setApercu] = useState<OppositionPreview | null>(null);
  const [demande, setDemande] = useState("");
  const [refus, setRefus] = useState<string | null>(null);

  if (!(session.data?.permissions.includes("oppositions:manage") ?? false)) return null;

  async function ouvrir() {
    setRefus(null);
    setApercu(null);
    setDemande(localToday());
    setOuverte(true);
    try {
      setApercu(await apiClient.previewOpposition({ athlete_id: athlete.id }));
    } catch {
      setRefus(ECHEC);
    }
  }

  async function confirmer() {
    setRefus(null);
    try {
      await appliquer.mutateAsync({ athlete_id: athlete.id, requested_on: demande });
      toast.success("Opposition appliquée : les résultats sont anonymes.");
      router.replace("/resultats");
    } catch {
      setRefus(ECHEC);
    }
  }

  return (
    <>
      <Button variant="secondary" onClick={ouvrir}>
        Appliquer une opposition
      </Button>

      {ouverte && (
        <Modal
          eyebrow="Droit d'opposition"
          title={`Anonymiser ${athlete.prenom} ${athlete.nom} ?`}
          onClose={() => (appliquer.isPending ? null : setOuverte(false))}
          footer={
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
              <Button variant="ghost" onClick={() => setOuverte(false)} disabled={appliquer.isPending}>
                Annuler
              </Button>
              <Button
                variant="destructive"
                onClick={confirmer}
                disabled={!apercu || !demande || appliquer.isPending}
              >
                {appliquer.isPending ? "Application…" : "Anonymiser définitivement"}
              </Button>
            </div>
          }
        >
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {refus && (
              <div role="alert">
                <Alert status="error" title="Opposition non appliquée">
                  {refus}
                </Alert>
              </div>
            )}
            {apercu ? (
              <p>
                {apercu.results > 1
                  ? `${apercu.results} résultats deviendront anonymes`
                  : `${apercu.results} résultat deviendra anonyme`}
                , et la fiche sera supprimée. Ce geste est définitif, et tout résultat importé ensuite à ce
                nom arrivera anonyme.
                {apercu.athletes > 1 &&
                  ` Attention : ${apercu.athletes} fiches portent le même nom et le même prénom, elles seront toutes anonymisées.`}
              </p>
            ) : (
              !refus && <p>Calcul des résultats concernés…</p>
            )}
            <div>
              <label
                htmlFor="opposition-demande"
                style={{ display: "block", marginBottom: 6, fontSize: 13, fontWeight: 700 }}
              >
                Date de la demande
              </label>
              <Input
                id="opposition-demande"
                type="date"
                max={localToday()}
                value={demande}
                onChange={(e) => setDemande(e.target.value)}
              />
            </div>
          </div>
        </Modal>
      )}
    </>
  );
}
