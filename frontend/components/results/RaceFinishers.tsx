"use client";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState, useTransition } from "react";
import { Card, SegmentedControl, PlaceBadge } from "@/components/tcn";
import { StatusBadge } from "@/components/results/StatusBadge";
import { isNonFinisher } from "@/lib/utils/raceOrder";
import { splitColumnsFromKeys } from "@/lib/utils/splits";
import { secondsFromHms } from "@/lib/utils/time";
import { SCOPE_CLUB, SCOPE_PARAM } from "@/lib/scope";
import { CLUB_NAME } from "@/lib/club";
import type { CourseSummary, Participation } from "@/lib/types";

// Colonnes fixes (rang, athlète, catég., sexe, temps total) + club en fin.
const BASE_COLS = "54px 1fr 70px 56px 100px";
const CLUB_COL = "1.1fr";

// Clé de tri du temps total : distincte de toute clé de split réelle
// (swim/t1/bike/t2/run/course1/course2), qui vivent dans `Participation.splits`
// alors que le temps total vit dans `Participation.total_time`.
const CLE_TEMPS_TOTAL = "__temps_total__";

export function RaceFinishers({
  participations,
  summary,
  total,
  page,
  pageSize,
  eventType,
}: {
  /** La tranche courante, **déjà ordonnée par le backend** — ne pas la retrier. */
  participations: Participation[];
  /** Synthèse de l'épreuve entière : indépendante de la recherche et du filtre. */
  summary: CourseSummary;
  /** Total de la sélection (recherche + filtre club), qui donne le nombre de pages. */
  total: number;
  page: number;
  /** `null` quand tout le classement a été demandé. */
  pageSize: number | null;
  eventType?: string | null;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [pending, startTransition] = useTransition();
  const rechercheUrl = searchParams.get("q") ?? "";
  const [recherche, setRecherche] = useState(rechercheUrl);
  const [derniereUrl, setDerniereUrl] = useState(rechercheUrl);
  // Tri optionnel côté client, déclenché par un clic sur l'en-tête d'un split
  // ou du temps total (#309) — sur la seule tranche affichée. `null` tant
  // qu'aucun en-tête n'a été cliqué : l'ordre reste alors celui du backend.
  // Recliquer sur le même en-tête inverse la direction ; cliquer sur un autre
  // en-tête repart en croissant.
  const [tri, setTri] = useState<{ cle: string; direction: "asc" | "desc" } | null>(null);

  function trierSur(cle: string) {
    setTri((precedent) =>
      precedent?.cle === cle
        ? { cle, direction: precedent.direction === "asc" ? "desc" : "asc" }
        : { cle, direction: "asc" }
    );
  }

  // L'URL est la vérité : après un « Précédent » du navigateur, le champ doit
  // suivre. Ajustement pendant le rendu plutôt qu'en effet — React le
  // recommande pour un état dérivé d'une valeur qui change.
  if (rechercheUrl !== derniereUrl) {
    setDerniereUrl(rechercheUrl);
    setRecherche(rechercheUrl);
  }

  const filtreClub = searchParams.get(SCOPE_PARAM) === SCOPE_CLUB;

  /** Construit une URL en repartant des paramètres courants. */
  function lienVers(modifications: Record<string, string | null>): string {
    const params = new URLSearchParams(searchParams.toString());
    for (const [cle, valeur] of Object.entries(modifications)) {
      if (valeur === null || valeur === "") params.delete(cle);
      else params.set(cle, valeur);
    }
    const query = params.toString();
    return `${pathname}${query ? `?${query}` : ""}`;
  }

  /**
   * Toute modification de la recherche ou du filtre remet à la première page :
   * une recherche à trois résultats atterrirait sinon sur une page vide.
   */
  function naviguer(modifications: Record<string, string | null>) {
    startTransition(() => router.push(lienVers({ ...modifications, page: null })));
  }

  // Les colonnes viennent de la synthèse et non des lignes affichées : sur vingt
  // lignes, elles changeraient d'une page à l'autre.
  const segments = splitColumnsFromKeys(eventType ?? "", summary.split_keys);
  const fcols = [BASE_COLS, ...segments.map((s) => (s.small ? "64px" : "80px")), CLUB_COL].join(" ");

  const nbPages = pageSize ? Math.max(1, Math.ceil(total / pageSize)) : 1;

  /** Temps (en secondes) du participant pour la colonne de tri active. */
  function temps(p: Participation, cle: string): number | null {
    return secondsFromHms(cle === CLE_TEMPS_TOTAL ? p.total_time : p.splits?.[cle]);
  }

  // Valeurs non temporelles (DNF/DNS/DSQ, segment non publié) envoyées en fin
  // de classement, croissant comme décroissant : ce n'est pas un temps nul, il
  // n'y a simplement rien à comparer. `sort` est stable (ES2019+) : les
  // égalités et les lignes non triées gardent l'ordre du backend.
  const lignes = tri
    ? [...participations].sort((a, b) => {
        const sa = temps(a, tri.cle);
        const sb = temps(b, tri.cle);
        if (sa == null) return sb == null ? 0 : 1;
        if (sb == null) return -1;
        return tri.direction === "asc" ? sa - sb : sb - sa;
      })
    : participations;

  return (
    <Card padding={0} style={{ overflow: "hidden" }}>
      <div style={{ padding: "20px 26px", borderBottom: "1px solid var(--tcn-border)", display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
        <div style={{ fontFamily: "var(--tcn-font-display)", fontSize: 22, color: "var(--tcn-ink)" }}>Classement</div>
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <form
            role="search"
            onSubmit={(e) => {
              e.preventDefault();
              naviguer({ q: recherche.trim() || null });
            }}
            style={{ display: "flex", gap: 6 }}
          >
            <label htmlFor="recherche-athlete" className="sr-only">
              Rechercher un athlète
            </label>
            <input
              id="recherche-athlete"
              type="search"
              value={recherche}
              onChange={(e) => setRecherche(e.target.value)}
              placeholder="Rechercher un athlète"
              style={{ height: 34, minWidth: 190, padding: "0 10px", fontSize: 13, borderRadius: 8, border: "1px solid var(--tcn-border)", background: "var(--tcn-surface)", color: "var(--tcn-ink)" }}
            />
            <button
              type="submit"
              style={{ height: 34, padding: "0 12px", fontSize: 13, fontWeight: 700, borderRadius: 8, border: "1px solid var(--tcn-border)", background: "var(--tcn-fill)", color: "var(--tcn-ink)", cursor: "pointer" }}
            >
              Chercher
            </button>
          </form>
          <SegmentedControl
            tone="ink"
            value={filtreClub ? "tcn" : "all"}
            onChange={(v) => naviguer({ [SCOPE_PARAM]: v === "tcn" ? SCOPE_CLUB : null })}
            options={[
              { value: "all", label: `Tous les coureurs (${summary.total})` },
              { value: "tcn", label: `${CLUB_NAME} (${summary.tcn_count})`, dot: true },
            ]}
          />
        </div>
      </div>
      <div
        style={{ overflowX: "auto" }}
        data-pending={pending || undefined}
        className="transition-opacity data-pending:opacity-60"
      >
        <div style={{ minWidth: 1080 }}>
          <div style={{ display: "grid", gridTemplateColumns: fcols, gap: "0 12px", padding: "12px 22px", fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".04em", color: "var(--tcn-text-faint)", borderBottom: "1px solid var(--tcn-border)" }}>
            <div>Rang</div><div>Athlète</div><div>Catég.</div><div>Sexe</div>
            <div>
              <EnteteTriable cle={CLE_TEMPS_TOTAL} libelle="Temps total" ariaSujet="temps total" tri={tri} onTrier={trierSur} />
            </div>
            {segments.map((s) => (
              <div key={s.key}>
                <EnteteTriable cle={s.key} libelle={s.label} ariaSujet={`temps ${s.label}`} tri={tri} onTrier={trierSur} />
              </div>
            ))}
            <div>Club</div>
          </div>
          {lignes.map((p) => {
            const own = p.is_tcn;
            const nf = isNonFinisher(p.status);
            const name = [p.athlete?.nom, p.athlete?.prenom].filter(Boolean).join(" ");
            const splits = p.splits ?? {};
            return (
              <div
                key={p.id}
                role="button"
                tabIndex={0}
                aria-label={`Voir le profil de ${name}`}
                onClick={() => router.push(`/athletes/${p.athlete?.id}`)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    router.push(`/athletes/${p.athlete?.id}`);
                  }
                }}
                className="tcn-rowlink"
                style={{ display: "grid", gridTemplateColumns: fcols, gap: "0 12px", alignItems: "center", padding: "12px 22px", borderBottom: "1px solid var(--tcn-border-faint)", borderLeft: `3px solid ${own ? "var(--tcn-orange)" : "transparent"}`, background: nf ? "color-mix(in srgb, var(--tcn-grey-400) 15%, transparent)" : undefined }}
              >
                <div>
                  {nf ? (
                    <StatusBadge status={p.status} />
                  ) : p.rank_overall != null ? (
                    <PlaceBadge place={p.rank_overall} style={{ minWidth: 28, fontSize: 16 }} />
                  ) : (
                    <span style={{ color: "var(--tcn-text-faint)" }}>—</span>
                  )}
                </div>
                <div style={{ fontSize: 14, fontWeight: 700, color: "var(--tcn-ink)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{name}</div>
                <div style={{ fontSize: 13, color: "var(--tcn-text-body)" }}>{p.category ?? "—"}</div>
                <div style={{ fontSize: 13, color: "var(--tcn-text-body)" }}>{genderShort(p.athlete?.gender)}</div>
                <div style={{ fontFamily: "var(--tcn-font-cond)", fontWeight: 700, fontSize: 15, color: "var(--tcn-ink)" }}>{p.total_time ?? "—"}</div>
                {segments.map((s) => (
                  <div key={s.key} style={{ fontSize: 13, fontWeight: s.small ? 400 : 600, color: s.small ? "var(--tcn-grey-400)" : "var(--tcn-text-body)" }}>
                    {splits[s.key] ?? "—"}
                  </div>
                ))}
                <div style={{ fontSize: 13, fontWeight: own ? 700 : 400, color: own ? "var(--tcn-orange)" : "var(--tcn-text-muted)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{p.club ?? "—"}</div>
              </div>
            );
          })}
          {participations.length === 0 && (
            <div style={{ padding: 30, textAlign: "center", color: "var(--tcn-text-faint)", fontSize: 14 }}>
              {page > nbPages ? (
                <>
                  Cette page n&apos;existe pas — le classement s&apos;arrête à la page {nbPages}.{" "}
                  <Link href={lienVers({ page: null })} style={{ fontWeight: 700, color: "var(--tcn-ink)" }}>
                    Revenir au début
                  </Link>
                </>
              ) : rechercheUrl || filtreClub ? (
                "Aucun athlète ne correspond à cette recherche."
              ) : (
                "Aucun participant à afficher."
              )}
            </div>
          )}
        </div>
      </div>

      {nbPages > 1 && <Pagination page={page} nbPages={nbPages} lienVers={lienVers} />}

      <div style={{ padding: "16px 24px", borderTop: "1px solid var(--tcn-border)", textAlign: "center", fontSize: 13, color: "var(--tcn-text-faint)" }}>
        {resumeEpreuve(summary)}
      </div>
    </Card>
  );
}

/**
 * Navigation par pages, en liens et non en boutons : ouvrables en nouvel onglet,
 * utilisables au clavier et fonctionnels avant hydratation.
 */
function Pagination({
  page,
  nbPages,
  lienVers,
}: {
  page: number;
  nbPages: number;
  lienVers: (modifications: Record<string, string | null>) => string;
}) {
  const style = {
    padding: "6px 14px",
    fontSize: 13,
    fontWeight: 700,
    borderRadius: 8,
    border: "1px solid var(--tcn-border)",
    color: "var(--tcn-ink)",
  } as const;
  const inactif = { ...style, color: "var(--tcn-text-faint)", opacity: 0.5 };
  // Hors bornes, « Précédent » ramène à la dernière page réelle : reculer d'un
  // cran depuis la page 99 999 ferait traverser 99 908 pages vides.
  const precedente = Math.min(page - 1, nbPages);

  return (
    <nav
      aria-label="Pagination du classement"
      style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 14, padding: "14px 24px", borderTop: "1px solid var(--tcn-border)" }}
    >
      {page > 1 ? (
        <Link
          href={lienVers({ page: precedente === 1 ? null : String(precedente) })}
          style={style}
          rel="prev"
        >
          ‹ Précédent
        </Link>
      ) : (
        <span style={inactif} aria-disabled="true">‹ Précédent</span>
      )}
      <span style={{ fontSize: 13, color: "var(--tcn-text-muted)" }} aria-current="page">
        Page {page} sur {nbPages}
      </span>
      {page < nbPages ? (
        <Link href={lienVers({ page: String(page + 1) })} style={style} rel="next">
          Suivant ›
        </Link>
      ) : (
        <span style={inactif} aria-disabled="true">Suivant ›</span>
      )}
    </nav>
  );
}

/**
 * Décompte de l'épreuve **entière**, distinct du nombre de lignes affichées :
 * « partants » n'est pas « finishers » (cf. issue #23).
 */
function resumeEpreuve(summary: CourseSummary): string {
  const { total, finishers, non_finishers: abandons, unknown } = summary;
  const parts = [
    `${total} partant${total > 1 ? "s" : ""}`,
    `${finishers} finisher${finishers > 1 ? "s" : ""}`,
  ];
  if (abandons > 0) parts.push(`${abandons} abandon${abandons > 1 ? "s" : ""}`);
  if (unknown > 0) parts.push(`${unknown} indéterminé${unknown > 1 ? "s" : ""}`);
  return parts.join(" · ");
}

/**
 * En-tête de colonne triable (temps total ou un split) : un clic trie en
 * croissant, recliquer sur la même colonne inverse en décroissant, cliquer sur
 * une autre colonne repart en croissant.
 */
function EnteteTriable({
  cle,
  libelle,
  ariaSujet,
  tri,
  onTrier,
}: {
  cle: string;
  libelle: string;
  ariaSujet: string;
  tri: { cle: string; direction: "asc" | "desc" } | null;
  onTrier: (cle: string) => void;
}) {
  const actif = tri?.cle === cle;
  const direction = actif ? tri.direction : null;
  const prochaineDirection = direction === "asc" ? "desc" : "asc";

  return (
    <button
      type="button"
      onClick={() => onTrier(cle)}
      aria-label={`Trier par ${ariaSujet}, ${prochaineDirection === "asc" ? "croissant" : "décroissant"}`}
      style={{
        font: "inherit",
        fontSize: 11,
        fontWeight: 700,
        textTransform: "uppercase",
        letterSpacing: ".04em",
        color: actif ? "var(--tcn-ink)" : "inherit",
        background: "none",
        border: "none",
        padding: 0,
        cursor: "pointer",
      }}
    >
      {libelle}
      {direction === "asc" ? " ▲" : direction === "desc" ? " ▼" : ""}
    </button>
  );
}

function genderShort(g: string | null | undefined): string {
  if (!g) return "—";
  const c = g.trim().toLowerCase()[0];
  if (c === "f" || c === "w") return "F";
  if (c === "m" || c === "h") return "M";
  return g;
}
