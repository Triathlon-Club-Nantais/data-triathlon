"use client";
import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Button, Modal } from "@/components/tcn";
import { DangerConfirm } from "@/components/admin/DangerConfirm";
import { useDetachParticipations } from "@/lib/queries/admin";
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
 * Deux pouvoirs, comme la route ; sans eux, rien n'est rendu.
 */
export function AthleteDetachAction({
  athleteId,
  athleteName,
  participations,
}: {
  athleteId: number;
  athleteName: string;
  participations: Participation[];
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

  if (!autorise || participations.length < 2) return null;

  const nombre = coches.size;
  const ficheVidee = nombre === participations.length;
  const envoiPossible = nombre > 0 && !ficheVidee;
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
      router.push(`/athletes/${nouvelle.id}`);
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
        onClick={() => setOuvert(true)}
        aria-label={`Séparer des résultats de ${athleteName}`}
      >
        Séparer des résultats
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
          <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 8 }}>
            {participations.map((p) => (
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
