"use client";
import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Button, Modal } from "@/components/tcn";
import { DangerConfirm } from "@/components/admin/DangerConfirm";
import { useAthleteResults, useDetachParticipations } from "@/lib/queries/admin";
import { useHydratedSession } from "@/lib/queries/auth";
import type { Participation } from "@/lib/types";
import { formatDate } from "@/lib/utils/date";

/**
 * « Séparer des résultats » : plusieurs personnes du même nom partagent la fiche
 * (#1209). Les résultats cochés partent sur une nouvelle fiche d'homonyme, que la
 * page ouvre ensuite.
 *
 * `DangerConfirm` déclaratif et non `useDangerConfirm` : la fiche athlète est
 * publique, hors de tout `DangerConfirmProvider` (patron de `CourseSourcesPanel`).
 * Deux pouvoirs, comme la route ; sans eux, rien n'est rendu. Seuls les
 * résultats que la fiche porte se séparent : là où elle n'est qu'équipière, le
 * résultat appartient au porteur du relais.
 *
 * Réutilisé par la revue d'identité (#1241) : sans `participations`, les
 * résultats de la fiche ne se lisent qu'à l'ouverture de la fenêtre ;
 * `preselectedIds` coche d'avance le résultat d'une ligne en conflit, et
 * `openNewRecord={false}` laisse l'admin sur la revue.
 */
export function AthleteDetachAction({
  athleteId,
  athleteName,
  participations,
  preselectedIds = [],
  label = "Séparer des résultats",
  ariaLabel = `Séparer des résultats de ${athleteName}`,
  openNewRecord = true,
}: {
  athleteId: number;
  athleteName: string;
  participations?: Participation[];
  preselectedIds?: number[];
  label?: string;
  ariaLabel?: string;
  openNewRecord?: boolean;
}) {
  const session = useHydratedSession();
  const pouvoirs = session.data?.permissions ?? [];
  const autorise = pouvoirs.includes("athletes:write") && pouvoirs.includes("participations:reassign");
  const [ouvert, setOuvert] = useState(false);
  const [coches, setCoches] = useState<Set<number>>(new Set());
  const [confirmation, setConfirmation] = useState(false);
  const declencheur = useRef<HTMLButtonElement>(null);
  const separation = useDetachParticipations();
  const router = useRouter();
  const lazyResults = useAthleteResults(athleteId, autorise && ouvert && participations === undefined);

  const portes = (participations ?? lazyResults.data ?? []).filter((p) => p.athlete.id === athleteId);
  if (!autorise || (participations !== undefined && portes.length < 2)) return null;

  const nombre = coches.size;
  // Avant la lecture différée, aucune liste : ni refus affiché, ni envoi possible.
  const ficheVidee = portes.length > 0 && nombre === portes.length;
  const envoiPossible = portes.length > 0 && nombre > 0 && !ficheVidee;
  const libelle = `${nombre} résultat${nombre > 1 ? "s" : ""}`;

  function basculer(id: number) {
    setCoches((avant) => {
      const apres = new Set(avant);
      if (apres.has(id)) apres.delete(id);
      else apres.add(id);
      return apres;
    });
  }

  function fermer() {
    setOuvert(false);
    setCoches(new Set());
  }

  async function separer() {
    try {
      const nouvelle = await separation.mutateAsync({ athleteId, participationIds: [...coches] });
      toast.success(`${libelle} séparé${nombre > 1 ? "s" : ""} vers une nouvelle fiche.`);
      setConfirmation(false);
      fermer();
      router.refresh();
      if (openNewRecord) router.push(`/athletes/${nouvelle.id}`);
    } catch (erreur) {
      toast.error((erreur as Error).message);
    }
  }

  return (
    <>
      <Button
        ref={declencheur}
        variant="secondary"
        size="sm"
        onClick={() => {
          setCoches(new Set(preselectedIds));
          setOuvert(true);
        }}
        aria-label={ariaLabel}
      >
        {label}
      </Button>

      {ouvert && !confirmation && (
        <Modal
          eyebrow="Fiche athlète"
          title="Séparer des résultats"
          onClose={fermer}
          footer={
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
              <Button variant="ghost" onClick={fermer}>
                Annuler
              </Button>
              <Button variant="primary" disabled={!envoiPossible} onClick={() => setConfirmation(true)}>
                Séparer vers une nouvelle fiche
              </Button>
            </div>
          }
        >
          <p style={{ margin: "0 0 12px", fontSize: 14, color: "var(--tcn-text-muted)" }}>
            Cochez les résultats d&apos;une autre personne nommée {athleteName}. Ils partiront sur une
            nouvelle fiche, distincte de celle-ci.
          </p>
          {participations === undefined && lazyResults.isPending && (
            <p role="status" style={{ margin: "0 0 12px", fontSize: 13, color: "var(--tcn-text-muted)" }}>
              Lecture des résultats…
            </p>
          )}
          {lazyResults.isError && (
            <p role="alert" style={{ margin: "0 0 12px", fontSize: 13, color: "var(--tcn-text-muted)" }}>
              Les résultats de la fiche n&apos;ont pas pu être lus. Fermez et réessayez.
            </p>
          )}
          <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 8 }}>
            {portes.map((p) => (
              <li key={p.id}>
                <label style={{ display: "flex", gap: 10, alignItems: "baseline", fontSize: 14, minHeight: 44 }}>
                  <input type="checkbox" checked={coches.has(p.id)} onChange={() => basculer(p.id)} />
                  <span>
                    {p.course.name}
                    <span style={{ color: "var(--tcn-text-faint)" }}>
                      {" · "}
                      {formatDate(p.course.event_date)}
                      {" · "}
                      {p.club ?? "Sans club"}
                      {(p.teammates?.length ?? 0) > 0 && " · relais, ses équipiers seront retirés"}
                    </span>
                  </span>
                </label>
              </li>
            ))}
          </ul>
          {ficheVidee && (
            <p role="status" style={{ margin: "12px 0 0", fontSize: 13, color: "var(--tcn-text-muted)" }}>
              La fiche doit garder au moins un résultat.
            </p>
          )}
        </Modal>
      )}

      <DangerConfirm
        open={confirmation}
        onOpenChange={(ouverte) => !ouverte && setConfirmation(false)}
        titre={`Séparer ${libelle} vers une nouvelle fiche ?`}
        description={`Une nouvelle fiche ${athleteName} est créée avec ces résultats. Les deux fiches sont jugées distinctes et ne seront plus proposées à la fusion.`}
        libelleAction="Séparer"
        enAttente={separation.isPending}
        onConfirm={separer}
        finalFocus={declencheur}
      />
    </>
  );
}
