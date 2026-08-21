import Link from "next/link";
import { PageHeader } from "@/components/layout/PageHeader";
import { PageShell } from "@/components/layout/PageShell";

/**
 * Écran d'absence — remplace le « 404 — This page could not be found. » anglais
 * de Next.js dans un document déclaré `lang="fr"` (`ETAT-1`, WCAG 2.2 3.1.1).
 *
 * Il sert **deux** cas et la copie doit être vraie des deux : les `notFound()`
 * des trois routes dynamiques (épreuve, athlète, participation) et toute URL
 * qui ne matche aucune route. D'où « cette page », et l'épreuve fusionnée ou
 * supprimée citée comme cause probable plutôt qu'affirmée — sur
 * `/athletes/[id]`, un backend injoignable atterrit aussi ici.
 *
 * Trois sorties, et non la carte : `/carte` reste masquée du rail (#10, #28)
 * tant que son rendu sans données n'a pas été vérifié, et un lien posé ici en
 * serait la première exposition publique.
 */
export default function NotFound() {
  return (
    <PageShell>
      <div className="space-y-6">
        <PageHeader
          eyebrow="Page introuvable"
          title="Cette page n'existe pas, ou n'existe plus"
          description="Le lien est peut-être périmé — une épreuve fusionnée ou supprimée — ou l'adresse a été recopiée de travers."
        />
        <nav aria-label="Où aller maintenant" className="flex flex-wrap gap-x-6 gap-y-3 text-sm font-semibold">
          <Link href="/resultats" className="inline-flex min-h-[24px] items-center underline">
            Voir les résultats
          </Link>
          <Link href="/ajouter" className="inline-flex min-h-[24px] items-center underline">
            Ajouter une épreuve
          </Link>
          <Link href="/dashboard" className="inline-flex min-h-[24px] items-center underline">
            Revenir au tableau de bord
          </Link>
        </nav>
      </div>
    </PageShell>
  );
}
