"use client";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState, useTransition } from "react";
import { Card, SegmentedControl, PlaceBadge, AnnonceStatut } from "@/components/tcn";
import { StatusBadge } from "@/components/results/StatusBadge";
import { isNonFinisher } from "@/lib/utils/raceOrder";
import { splitColumnsFromKeys } from "@/lib/utils/splits";
import { secondsFromHms } from "@/lib/utils/time";
import { genderShort } from "@/lib/utils/format";
import { EmptyState } from "@/components/ui/empty-state";
import { ClassementPagination } from "@/components/results/ClassementPagination";
import { PAGE_SIZE_DEFAUT, PAGE_SIZE_PARAM, parsePageSize } from "@/lib/pageSize";
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

/**
 * Une ligne de finisher ouvre le détail de **ce résultat**, pas le profil de
 * l'athlète : depuis un classement, la question est « comment s'est passée
 * cette course », pas « qui est ce coureur ».
 */
function detailHref(p: Participation): string {
  return `/courses/${p.course?.id}/participations/${p.id}`;
}

/**
 * Cellule d'un inter — **ne rend que ce qui se lit comme une durée** (#472).
 *
 * Le repli `—` ne couvrait que l'absence de valeur, jamais l'impossible : un
 * `0-2:-15:00` (observé sur la course 340) partait à l'écran tel quel, que rien
 * ne distinguait d'un chronomètre exact. Il devient un manque **signalé** — ni
 * la chaîne brute, ni un silence qui ferait croire que le chronométreur n'a rien
 * publié. Même lecture que le tri, qui écarte déjà ces valeurs faute de pouvoir
 * les comparer.
 */
function CelluleInter({ valeur, small }: { valeur?: string; small?: boolean }) {
  const style = {
    fontSize: 13,
    fontWeight: small ? 400 : 600,
    color: small ? "var(--tcn-grey-400)" : "var(--tcn-text-body)",
  };
  if (valeur && secondsFromHms(valeur) == null) {
    const motif = `Temps illisible chez le chronométreur (« ${valeur} ») — la donnée existe, mais ce n'est pas un temps.`;
    return (
      <div style={style}>
        —{" "}
        <span
          // `role="img"` : le marqueur informe, il ne commande rien.
          role="img"
          title={motif}
          aria-label={motif}
          style={{ color: "var(--tcn-text-faint)", cursor: "help", userSelect: "none" }}
        >
          ⚠
        </span>
      </div>
    );
  }
  return <div style={style}>{valeur ?? "—"}</div>;
}

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
  // La taille vient de l'URL, pas de la prop `pageSize` : sous `all`, le
  // backend renvoie `null` et le sélecteur n'aurait plus quoi afficher.
  const tailleCourante = parsePageSize(searchParams.get(PAGE_SIZE_PARAM));

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

  /** Saut direct à une page, la recherche et le filtre en cours conservés. */
  function naviguerPage(n: number) {
    startTransition(() => router.push(lienVers({ page: n === 1 ? null : String(n) })));
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

  // WCAG 4.1.3 (#477) : le tri par en-tête réordonne les 1080 px du tableau
  // sans déplacer le focus — sans cette annonce, un lecteur d'écran ne le voit
  // pas passer, pas plus que le nouveau décompte après une recherche.
  const libelleTri = tri
    ? tri.cle === CLE_TEMPS_TOTAL
      ? "temps total"
      : `temps ${segments.find((s) => s.key === tri.cle)?.label ?? tri.cle}`
    : null;
  const texteAnnonce =
    `${lignes.length} résultat${lignes.length > 1 ? "s" : ""} affiché${lignes.length > 1 ? "s" : ""}` +
    (libelleTri ? `, trié par ${libelleTri}, ${tri!.direction === "asc" ? "croissant" : "décroissant"}` : "");

  return (
    <Card padding={0} style={{ overflow: "hidden" }}>
      <AnnonceStatut texte={texteAnnonce} />
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
              { value: "all", label: `Tous les participants (${summary.total})` },
              { value: "tcn", label: `${CLUB_NAME} (${summary.tcn_count})`, dot: true },
            ]}
          />
        </div>
      </div>
      {(rechercheUrl || filtreClub) && (
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", padding: "10px 26px", borderBottom: "1px solid var(--tcn-border)", fontSize: 13, color: "var(--tcn-text-body)" }}>
          <span>{libelleSelection(total, summary.total, rechercheUrl, filtreClub)}</span>
          <button
            type="button"
            onClick={() => naviguer({ q: null, [SCOPE_PARAM]: null })}
            style={{ background: "none", border: "none", padding: "4px 0", minHeight: 24, font: "inherit", fontWeight: 700, color: "var(--tcn-ink)", textDecoration: "underline", cursor: "pointer" }}
          >
            Effacer
          </button>
        </div>
      )}
      <div
        style={{ overflowX: "auto" }}
        data-pending={pending || undefined}
        className="transition-opacity data-pending:opacity-60"
      >
        <div style={{ minWidth: 1080 }}>
          <div style={{ display: "grid", gridTemplateColumns: fcols, gap: "0 12px", alignItems: "center", padding: "12px 22px", fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".04em", color: "var(--tcn-text-faint)", borderBottom: "1px solid var(--tcn-border)" }}>
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
                aria-label={`Voir le détail du résultat de ${name}`}
                onClick={() => router.push(detailHref(p))}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    router.push(detailHref(p));
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
                  <CelluleInter key={s.key} valeur={splits[s.key]} small={s.small} />
                ))}
                <div style={{ fontSize: 13, fontWeight: own ? 700 : 400, color: own ? "var(--tcn-orange-deeper)" : "var(--tcn-text-muted)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{p.club ?? "—"}</div>
              </div>
            );
          })}
          {participations.length === 0 && (
            page > nbPages ? (
              <EmptyState
                bare
                title="Cette page n'existe pas"
                description={`le classement s'arrête à la page ${nbPages}`}
                action={
                  <Link href={lienVers({ page: null })} style={{ fontWeight: 700, color: "var(--tcn-ink)" }}>
                    Revenir au début
                  </Link>
                }
              />
            ) : rechercheUrl || filtreClub ? (
              <EmptyState
                bare
                title="Aucun athlète ne correspond à cette recherche"
                action={
                  <button
                    type="button"
                    onClick={() => naviguer({ q: null, [SCOPE_PARAM]: null })}
                    style={{ background: "none", border: "none", padding: 0, font: "inherit", fontWeight: 700, color: "var(--tcn-ink)", cursor: "pointer" }}
                  >
                    Effacer la recherche
                  </button>
                }
              />
            ) : (
              <EmptyState bare title="Aucun participant à afficher" />
            )
          )}
        </div>
      </div>

      <ClassementPagination
        page={page}
        nbPages={nbPages}
        lienVers={lienVers}
        tailleCourante={tailleCourante}
        onTaille={(taille) =>
          naviguer({ [PAGE_SIZE_PARAM]: taille === PAGE_SIZE_DEFAUT ? null : String(taille) })
        }
        onAllerPage={naviguerPage}
      />

      <div style={{ padding: "16px 24px", borderTop: "1px solid var(--tcn-border)", textAlign: "center", fontSize: 13, color: "var(--tcn-text-faint)" }}>
        <span>Sur l&apos;ensemble de l&apos;épreuve : </span>
        <span>{resumeEpreuve(summary)}</span>
      </div>
    </Card>
  );
}

/**
 * Cadre de la vue filtrée : ce qu'on regarde, et sur quoi.
 *
 * `total` est le total de la **sélection**, `totalEpreuve` celui de l'épreuve
 * entière — c'est leur opposition qui manquait, l'écran affirmant « 498
 * participants » sous deux lignes de résultats.
 */
function libelleSelection(total: number, totalEpreuve: number, recherche: string, filtreClub: boolean): string {
  const tete = `${total} résultat${total > 1 ? "s" : ""} sur ${totalEpreuve}`;
  const morceaux = [];
  if (recherche) morceaux.push(`pour « ${recherche} »`);
  if (filtreClub) morceaux.push(`du ${CLUB_NAME}`);
  return `${tete} ${morceaux.join(", ")}`;
}

/**
 * Décompte de l'épreuve **entière**, distinct du nombre de lignes affichées.
 *
 * « participants », pas « partants » (#322) : `summary.total` additionne
 * finishers, abandons (dnf), non-partants (dns), disqualifiés (dsq) et
 * indéterminés — il compte donc tous ceux qui figurent sur l'épreuve, y
 * compris ceux qui n'ont jamais pris le départ. La distinction que posait #23
 * reste entière, un participant n'est pas un finisher ; seul le mot était
 * faux. Les trois premiers étaient agrégés sous un seul « abandons » avant
 * #331 — un DNS n'a jamais couru, un DSQ a fini disqualifié.
 */
function resumeEpreuve(summary: CourseSummary): string {
  const { total, finishers, dnf, dns, dsq, unknown } = summary;
  const parts = [
    `${total} participant${total > 1 ? "s" : ""}`,
    `${finishers} finisher${finishers > 1 ? "s" : ""}`,
  ];
  if (dnf > 0) parts.push(`${dnf} abandon${dnf > 1 ? "s" : ""}`);
  if (dns > 0) parts.push(`${dns} non-partant${dns > 1 ? "s" : ""}`);
  if (dsq > 0) parts.push(`${dsq} disqualifié${dsq > 1 ? "s" : ""}`);
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
      // `padding` + `minHeight: 24` : plancher tactile WCAG 2.2 2.5.8, contre
      // 11 px sans padding avant #479.
      style={{
        font: "inherit",
        fontSize: 11,
        fontWeight: 700,
        textTransform: "uppercase",
        letterSpacing: ".04em",
        color: actif ? "var(--tcn-ink)" : "inherit",
        background: "none",
        border: "none",
        padding: "4px 0",
        minHeight: 24,
        display: "inline-flex",
        alignItems: "center",
        cursor: "pointer",
      }}
    >
      {libelle}
      {direction === "asc" ? " ▲" : direction === "desc" ? " ▼" : ""}
    </button>
  );
}

