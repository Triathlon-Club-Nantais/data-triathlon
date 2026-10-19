import Link from "next/link";
import { Card, Eyebrow } from "@/components/tcn";
import { ecart, formatTempsTotal, type ChiffresSaison } from "@/lib/mon-espace";

function signe(valeur: number, unite = ""): string {
  if (valeur === 0) return "=";
  return `${valeur > 0 ? "+" : "−"}${Math.abs(valeur)}${unite}`;
}

/** « Mes chiffres » de Mon espace : cinq chiffres de la sélection, écart face à la saison précédente à date égale quand `precedent` est fourni. */
export function MesChiffres({ courant, precedent }: { courant: ChiffresSaison; precedent: ChiffresSaison | null }) {
  const chiffres: { libelle: string; valeur: string; ecart: string | null }[] = [
    { libelle: "Épreuves", valeur: String(courant.epreuves), ecart: precedent && signe(ecart(courant.epreuves, precedent.epreuves)) },
    { libelle: "Podiums", valeur: String(courant.podiums), ecart: precedent && signe(ecart(courant.podiums, precedent.podiums)) },
    { libelle: "Kilomètres", valeur: String(Math.round(courant.km)), ecart: precedent && signe(Math.round(ecart(courant.km, precedent.km))) },
    {
      libelle: "Temps en course",
      valeur: formatTempsTotal(courant.tempsSecondes),
      ecart: precedent && signe(Math.round(ecart(courant.tempsSecondes, precedent.tempsSecondes) / 3600), " h"),
    },
    {
      libelle: "Meilleur classement",
      valeur: courant.meilleurRatio === null ? "n/d" : `Top ${courant.meilleurRatio} %`,
      ecart:
        precedent && courant.meilleurRatio !== null && precedent.meilleurRatio !== null
          ? signe(ecart(courant.meilleurRatio, precedent.meilleurRatio), " pts")
          : null,
    },
  ];

  return (
    <Card padding={20}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
        <Eyebrow>Mes chiffres</Eyebrow>
        <Link href="/mon-espace/recap" className="tcn-cible-tactile underline underline-offset-2" style={{ fontSize: 14 }}>
          Récap de la saison passée
        </Link>
      </div>
      <dl className="grid grid-cols-2 gap-4 sm:grid-cols-5" style={{ margin: "14px 0 0" }}>
        {chiffres.map((chiffre) => (
          <div key={chiffre.libelle} style={{ minWidth: 0 }}>
            <dt style={{ fontSize: 12, color: "var(--tcn-text-muted)" }}>{chiffre.libelle}</dt>
            <dd style={{ margin: 0, fontFamily: "var(--tcn-font-display)", fontSize: 26, lineHeight: 1.1, color: "var(--tcn-ink)" }}>
              {chiffre.valeur}
            </dd>
            {chiffre.ecart && (
              <dd data-testid="ecart" style={{ margin: 0, fontSize: 12, color: "var(--tcn-text-muted)" }}>
                {chiffre.ecart}
              </dd>
            )}
          </div>
        ))}
      </dl>
    </Card>
  );
}
