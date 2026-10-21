import Link from "next/link";
import { Card, Eyebrow } from "@/components/tcn";
import { ecart, formatTempsTotal, type ChiffresSaison } from "@/lib/mon-espace";

function signe(valeur: number, unite = ""): string {
  if (valeur === 0) return "=";
  return `${valeur > 0 ? "+" : "−"}${Math.abs(valeur)}${unite}`;
}

// Un top % plus petit est une amélioration : le signe brut se lirait comme une perte.
function ecartClassement(valeur: number): string {
  if (valeur === 0) return "=";
  return `${valeur < 0 ? "mieux" : "moins bien"} de ${Math.abs(valeur)} pts`;
}

/** « Mes chiffres » de Mon espace : cinq chiffres de la sélection, écart face à la saison précédente à date égale quand `precedent` est fourni. */
export function MesChiffres({ courant, precedent }: { courant: ChiffresSaison; precedent: ChiffresSaison | null }) {
  const kmInconnus = courant.epreuves > 0 && courant.km === 0;
  const kmIncomplets = courant.sansDistance > 0 || (precedent?.sansDistance ?? 0) > 0;
  const chiffres: { libelle: string; valeur: string; ecart: string | null; note?: string; etiquette?: string; prefixe?: string }[] = [
    { libelle: "Épreuves", valeur: String(courant.epreuves), ecart: precedent && signe(ecart(courant.epreuves, precedent.epreuves)) },
    { libelle: "Podiums", valeur: String(courant.podiums), ecart: precedent && signe(ecart(courant.podiums, precedent.podiums)) },
    {
      libelle: "Kilomètres",
      valeur: kmInconnus ? "—" : String(Math.round(courant.km)),
      prefixe: courant.sansDistance > 0 && !kmInconnus ? "au moins" : undefined,
      etiquette: kmInconnus ? "Distance inconnue" : undefined,
      note: courant.sansDistance > 0 ? `${courant.sansDistance} épreuve${courant.sansDistance > 1 ? "s" : ""} sans distance` : undefined,
      ecart: precedent && !kmIncomplets ? signe(Math.round(ecart(courant.km, precedent.km))) : null,
    },
    {
      libelle: "Temps en course",
      valeur: formatTempsTotal(courant.tempsSecondes),
      ecart: precedent && signe(Math.round(ecart(courant.tempsSecondes, precedent.tempsSecondes) / 3600), " h"),
    },
    {
      libelle: "Meilleur classement",
      valeur: courant.meilleurRatio === null ? "Pas encore de classement" : `Top ${courant.meilleurRatio} %`,
      ecart:
        precedent && courant.meilleurRatio !== null && precedent.meilleurRatio !== null
          ? ecartClassement(ecart(courant.meilleurRatio, precedent.meilleurRatio))
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
      <dl className="grid grid-cols-[repeat(auto-fit,minmax(8rem,1fr))] gap-4" style={{ margin: "14px 0 0" }}>
        {chiffres.map((chiffre) => (
          <div key={chiffre.libelle} style={{ minWidth: 0 }}>
            <dt style={{ fontSize: 12, color: "var(--tcn-text-muted)" }}>{chiffre.libelle}</dt>
            <dd style={{ margin: 0, fontFamily: "var(--tcn-font-display)", fontSize: 26, lineHeight: 1.1, color: "var(--tcn-ink)" }}>
              {chiffre.prefixe && <span style={{ display: "block", fontFamily: "var(--tcn-font-body)", fontSize: 12, lineHeight: 1.2, color: "var(--tcn-text-muted)" }}>{chiffre.prefixe}{" "}</span>}
              {chiffre.etiquette ? (
                <>
                  <span aria-hidden="true">{chiffre.valeur}</span>
                  <span className="sr-only">{chiffre.etiquette}</span>
                </>
              ) : (
                chiffre.valeur
              )}
            </dd>
            {chiffre.note && <dd style={{ margin: 0, fontSize: 12, color: "var(--tcn-text-muted)" }}>{chiffre.note}</dd>}
            {chiffre.ecart && (
              <dd data-testid="ecart" style={{ margin: 0, fontSize: 12, color: "var(--tcn-text-muted)" }}>
                {chiffre.ecart}
              </dd>
            )}
          </div>
        ))}
      </dl>
      {precedent && <p style={{ margin: "12px 0 0", fontSize: 12, color: "var(--tcn-text-muted)" }}>Écart face à la saison précédente, à date égale</p>}
    </Card>
  );
}
