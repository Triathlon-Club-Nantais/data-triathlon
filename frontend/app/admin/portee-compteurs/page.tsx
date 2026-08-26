"use client";
import { PageHeader } from "@/components/layout/PageHeader";
import { ecran } from "@/components/layout/nav.config";
import { PageShell } from "@/components/layout/PageShell";
import { CounterScopeCard } from "@/components/admin/CounterScopeCard";
import { CLUB_NAME } from "@/lib/club";
import { useCounterScope } from "@/lib/queries/admin";

/**
 * Ce que les compteurs comptent (#95).
 *
 * Deux listes en une page, et une seule lecture pour les deux : elles se
 * comprennent ensemble — l'une dit quelles disciplines sortent des compteurs de
 * triathlon, l'autre sous quelles orthographes un résultat est du club.
 *
 * Chaque liste porte sa règle en une phrase. Ce n'est pas de la décoration :
 * les deux se comportent à l'inverse l'une de l'autre — une discipline absente
 * de la première est **comptée**, un libellé absent de la seconde ne l'est
 * **pas** — et rien dans l'écran ne le laisse deviner.
 */
export default function AdminPorteeCompteursPage() {
  const { data, isLoading, error } = useCounterScope();

  return (
    <PageShell>
      <div className="space-y-10">
        <PageHeader {...ecran("/admin/portee-compteurs")} />
        <CounterScopeCard
          kind="club-labels"
          titre="Libellés du club"
          regle={
            <>
              Les orthographes sous lesquelles un chronométreur désigne le club.
              Un résultat n&apos;est compté comme résultat du club que si son libellé
              figure ici, <strong>à l&apos;identique</strong> — la comparaison ignore
              la casse et les espaces, mais « {CLUB_NAME} Sud » n&apos;est pas «{" "}
              {CLUB_NAME} ».
            </>
          }
          entrees={data?.club_labels}
          isLoading={isLoading}
          error={error}
          libelleChamp="Nouveau libellé"
          placeholder="TRIATHLON CLUB NANTAIS 44"
        />
        <CounterScopeCard
          kind="disciplines"
          titre="Disciplines hors compteurs"
          regle={
            <>
              Les disciplines que le bouton « Inclure les autres disciplines »
              retire des compteurs. C&apos;est une liste d&apos;<strong>exclusion</strong>{" "}
              : une discipline qui n&apos;y figure pas est comptée, y compris une
              discipline apparue depuis.
            </>
          }
          entrees={data?.disciplines}
          isLoading={isLoading}
          error={error}
          libelleChamp="Discipline à exclure"
          placeholder="trail"
        />
      </div>
    </PageShell>
  );
}
