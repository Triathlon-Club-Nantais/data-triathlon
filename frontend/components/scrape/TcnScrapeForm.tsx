"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Card, Input, Button, Alert } from "@/components/tcn";
import { apiClient } from "@/lib/api/client";
import { eventTypeLabel } from "@/lib/constants";
import { eventTypeColor } from "@/lib/sport-colors";
import { formatEventName } from "@/lib/utils/event";
import { isHttpUrl } from "@/lib/utils/url";
import { useSaveParticipation } from "@/lib/queries/participations";
import { useImportStream } from "@/hooks/useImportStream";
import { ProviderDetector } from "./ProviderDetector";
import { ManualResultForm } from "./ManualResultForm";
import type { ImportedCourse, ScrapedPreview } from "@/lib/types";

export function TcnScrapeForm() {
  const [url, setUrl] = useState("");
  const [manual, setManual] = useState(false);
  const reportedRef = useRef<string | null>(null);
  const refreshedRef = useRef<string | null>(null);
  const router = useRouter();

  const save = useSaveParticipation();
  const importStream = useImportStream();
  const {
    phase, error, running, imported, skipped, total, progress, cached, message, courses,
    heatIndex, heatsScrapingTotal, heatLabel,
  } = importStream.state;

  const isDuplicate = phase === "done" && (cached || (imported === 0 && skipped > 0));

  // Défense en profondeur alignée sur le backend (`ScrapeRequest.url: HttpUrl`,
  // 422 dès la porte, cf. `schemas/scrape.py`) : on filtre côté UI pour ne pas
  // envoyer une requête qu'on sait invalide, et pour rendre la contrainte
  // visible avant clic. `isHttpUrl` accepte `http(s)` et rejette `javascript:`,
  // `data:`, `ftp:`, chaînes vides et non-URL.
  const trimmed = url.trim();
  const urlIsValid = isHttpUrl(trimmed);
  const showUrlError = trimmed.length > 0 && !urlIsValid;

  const submit = useCallback(() => {
    const v = url.trim();
    if (!v || running) return;
    if (!isHttpUrl(v)) return;
    reportedRef.current = null;
    refreshedRef.current = null;
    setManual(false);
    importStream.start(v);
  }, [url, running, importStream]);

  // Sur échec réel : signaler le fournisseur + proposer la saisie manuelle.
  useEffect(() => {
    if (phase !== "error" || reportedRef.current === url) return;
    reportedRef.current = url;
    toast.error(error ?? "Import impossible");
    apiClient.reportPendingProvider(url).catch(() => {});
    setManual(true);
  }, [phase, error, url]);

  // Après un import réel, invalider le cache RSC de la page pour que la carte
  // « Derniers résultats enregistrés » (rendue côté serveur dans /ajouter) reflète
  // la nouvelle épreuve sans F5 manuel. Sur doublon (cache TTL frais), rien à
  // rafraîchir. Le ref garde l'URL déjà rafraîchie, réinitialisé au submit
  // suivant — sinon un re-render sur `phase === "done"` rappellerait refresh.
  useEffect(() => {
    if (phase !== "done" || isDuplicate) return;
    if (refreshedRef.current === url) return;
    refreshedRef.current = url;
    router.refresh();
  }, [phase, isDuplicate, url, router]);

  const persist = useCallback(
    async (data: Partial<ScrapedPreview>) => {
      try {
        await save.mutateAsync(data);
        toast.success("Résultat enregistré.");
        setManual(false);
      } catch (e) {
        toast.error((e as Error).message);
      }
    },
    [save],
  );

  const inputStatus = showUrlError
    ? "error"
    : isDuplicate
      ? "error"
      : phase === "error"
        ? "warning"
        : running
          ? "active"
          : "default";

  return (
    <>
      <Card padding={32} style={{ marginBottom: 22 }}>
        <div style={{ fontFamily: "var(--tcn-font-display)", fontSize: 22, color: "var(--tcn-ink)", marginBottom: 5 }}>
          Colle ici l&apos;adresse des résultats de ton triathlon
        </div>
        <div style={{ fontSize: 14, color: "var(--tcn-text-muted)", fontWeight: 500, marginBottom: 18 }}>
          Le lien vers la page de résultats officielle du chronométreur (PDF, site web…)
        </div>
        <div style={{ display: "flex", gap: 12, alignItems: "flex-start", flexWrap: "wrap" }}>
          <div style={{ flex: 1, minWidth: 260 }}>
            <Input
              value={url}
              status={inputStatus}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && submit()}
              placeholder="https://résultats-chrono.fr/triathlon-vertou-2026"
              type="url"
              inputMode="url"
              aria-invalid={showUrlError || undefined}
              aria-describedby={showUrlError ? "scrape-url-error" : undefined}
            />
            {showUrlError && (
              <div
                id="scrape-url-error"
                role="alert"
                style={{ marginTop: 6, fontSize: 13, color: "var(--tcn-danger-text, var(--tcn-danger-border))", fontWeight: 500 }}
              >
                Cette adresse n&apos;est pas une URL valide (elle doit commencer par http:// ou https://).
              </div>
            )}
            <div style={{ marginTop: 8 }}>
              <ProviderDetector url={url} />
            </div>
          </div>
          <Button size="lg" onClick={submit} disabled={running || !urlIsValid} iconRight={<span>→</span>} style={{ borderRadius: "var(--tcn-radius-xl)" }}>
            {running ? "Import en cours…" : "Enregistrer les résultats"}
          </Button>
        </div>

        {(phase === "scraping" || phase === "saving") && (
          <div style={{ marginTop: 14 }}>
            <ImportBar
              phase={phase}
              progress={progress}
              total={total}
              imported={imported}
              skipped={skipped}
              message={message}
              heatIndex={heatIndex}
              heatsScrapingTotal={heatsScrapingTotal}
              heatLabel={heatLabel}
            />
          </div>
        )}

        {phase === "done" && !isDuplicate && (
          <div style={{ marginTop: 14 }}>
            <Alert status="success" title="Résultats enregistrés avec succès !">
              {imported} résultat{imported > 1 ? "s" : ""} ajouté{imported > 1 ? "s" : ""}
              {skipped > 0 ? ` · ${skipped} déjà présent${skipped > 1 ? "s" : ""}` : ""}. Les statistiques du club ont été mises à jour.
              <CourseNavigator courses={courses} />
            </Alert>
          </div>
        )}
        {isDuplicate && (
          <div style={{ marginTop: 14 }}>
            <Alert status="error" title="Résultats déjà enregistrés">
              Ces résultats ont déjà été ajoutés. Les statistiques sont à jour ({skipped} participants en base).
              <CourseNavigator courses={courses} />
            </Alert>
          </div>
        )}
        {phase === "error" && (
          <div style={{ marginTop: 14 }}>
            <Alert
              status="warning"
              title="Impossible d'importer automatiquement"
              action={<Button variant="secondary" size="sm" onClick={() => setManual(true)}>Saisie manuelle</Button>}
            >
              {error ?? "Le lien fourni n'a pas pu être lu."} Tu peux saisir ta participation manuellement.
            </Alert>
          </div>
        )}
      </Card>

      {manual && (
        <Card padding={30} style={{ border: "1.5px solid var(--tcn-warning-border)", marginBottom: 22 }}>
          <div style={{ fontFamily: "var(--tcn-font-display)", fontSize: 22, color: "var(--tcn-ink)", marginBottom: 6 }}>Saisie manuelle de ta participation</div>
          <div style={{ fontSize: 14, color: "var(--tcn-text-muted)", marginBottom: 22 }}>Complète les champs ci-dessous. Ta participation sera bien enregistrée.</div>
          <ManualResultForm defaultUrl={url} onSubmit={persist} submitting={save.isPending} />
        </Card>
      )}
    </>
  );
}

/** Bouton d'action TCN rendu en `<a>` : mêmes styles que `Button variant="primary"`,
 *  mais navigable au clavier et par les crawlers. Utilisé pour aller vers /courses/{id}
 *  depuis les alertes de fin d'import (#135).
 *
 *  Les styles étaient recopiés à la main tant qu'ils vivaient en ligne dans
 *  `tcn/Button` ; depuis #299 ils sont en classes, donc il suffit de les porter —
 *  et le focus, le survol et le blanc à 3,68:1 se corrigent ici du même coup.
 */
function PrimaryLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link href={href} className="tcn-btn tcn-btn--md tcn-btn--primary">
      {children}
    </Link>
  );
}

/** Point d'entrée vers les résultats d'un import.
 *
 *  - 0 course : rien (import vide ou en erreur).
 *  - 1 course : un unique bouton primary, filant droit vers `/courses/{id}`.
 *  - N courses (heats Klikego, Wiclax, RaceResult multi-listes) : un sélecteur
 *    pour choisir la course + un bouton `Voir les résultats` — plus lisible
 *    qu'une grille de N boutons quand N dépasse 3-4.
 */
function CourseNavigator({ courses }: { courses: ImportedCourse[] }) {
  // Sélection brute : ce que l'utilisateur a cliqué (vide au premier rendu).
  // La valeur d'affichage est **dérivée** ci-dessous — pas d'`useEffect`
  // pour la synchroniser à `courses`, car un setState dans effect cascade
  // le rendu et déclenche l'erreur `react-hooks/set-state-in-effect`.
  const [selectedId, setSelectedId] = useState<string>("");

  if (courses.length === 0) return null;

  // Fallback à la 1re course tant que l'utilisateur n'a rien choisi, **et**
  // si sa sélection ne fait plus partie des courses (scénario improbable :
  // le SSE re-yield une phase `done` sur une nouvelle épreuve).
  const stillPresent = courses.some((c) => String(c.id) === selectedId);
  const effectiveId = stillPresent ? selectedId : String(courses[0].id);

  if (courses.length === 1) {
    const c = courses[0];
    return (
      <div style={{ marginTop: 12 }}>
        <PrimaryLink href={`/courses/${c.id}`}>
          Voir les résultats de « {formatEventName(c.name, Boolean(c.is_relay))} » <span aria-hidden="true">→</span>
        </PrimaryLink>
      </div>
    );
  }

  const selectedCourse = courses.find((c) => String(c.id) === effectiveId) ?? courses[0];

  return (
    <div style={{ marginTop: 12 }}>
      <div
        style={{
          fontFamily: "var(--tcn-font-cond)",
          fontSize: 12,
          fontWeight: 700,
          letterSpacing: "var(--tcn-eyebrow-tracking)",
          textTransform: "uppercase",
          color: "var(--tcn-orange)",
          marginBottom: 8,
        }}
      >
        {courses.length} courses importées
      </div>
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          gap: 10,
        }}
      >
        <CourseSelectField
          courses={courses}
          selectedId={effectiveId}
          selectedCourse={selectedCourse}
          onChange={setSelectedId}
        />
        <PrimaryLink href={`/courses/${effectiveId}`}>
          Voir les résultats <span aria-hidden="true">→</span>
        </PrimaryLink>
      </div>
    </div>
  );
}

/** `<select>` natif restylé TCN : bord épais, pastille de discipline colorée
 *  à gauche, chevron custom, focus visible orange. Prend la variante
 *  « Input » (bg `--tcn-fill`, radius XL, transition sur `border-color`) pour
 *  rester cohérent avec le champ URL juste au-dessus.
 */
function CourseSelectField({
  courses,
  selectedId,
  selectedCourse,
  onChange,
}: {
  courses: ImportedCourse[];
  selectedId: string;
  selectedCourse: ImportedCourse;
  onChange: (id: string) => void;
}) {
  const [focused, setFocused] = useState(false);
  const dotColor = eventTypeColor(selectedCourse.event_type);
  return (
    <label
      style={{
        position: "relative",
        display: "inline-flex",
        alignItems: "center",
        gap: 10,
        minWidth: 320,
        flex: "1 1 320px",
        padding: "12px 42px 12px 16px",
        background: "var(--tcn-fill)",
        border: `1.5px solid ${focused ? "var(--tcn-orange)" : "var(--tcn-border)"}`,
        borderRadius: "var(--tcn-radius-xl)",
        transition: "border-color var(--tcn-dur-fast)",
        cursor: "pointer",
      }}
    >
      <span
        aria-hidden="true"
        style={{
          flex: "none",
          width: 10,
          height: 10,
          borderRadius: 999,
          background: dotColor,
          boxShadow: "0 0 0 3px color-mix(in oklch, " + dotColor + " 15%, transparent)",
        }}
      />
      <span
        style={{
          flex: 1,
          minWidth: 0,
          fontFamily: "var(--tcn-font-body)",
          fontSize: 15,
          fontWeight: 600,
          color: "var(--tcn-ink)",
          whiteSpace: "nowrap",
          overflow: "hidden",
          textOverflow: "ellipsis",
        }}
      >
        {formatEventName(selectedCourse.name, Boolean(selectedCourse.is_relay))}
        <span style={{ color: "var(--tcn-text-muted)", fontWeight: 500 }}>
          {" · "}
          {eventTypeLabel(selectedCourse.event_type)}
        </span>
      </span>
      <span
        aria-hidden="true"
        style={{
          position: "absolute",
          right: 16,
          top: "50%",
          transform: "translateY(-50%)",
          color: "var(--tcn-text-muted)",
          fontSize: 12,
          fontWeight: 800,
          pointerEvents: "none",
        }}
      >
        ▾
      </span>
      <select
        aria-label="Choisir la course à consulter"
        value={selectedId}
        onChange={(e) => onChange(e.target.value)}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        style={{
          position: "absolute",
          inset: 0,
          width: "100%",
          height: "100%",
          opacity: 0,
          cursor: "pointer",
          border: "none",
          background: "transparent",
          appearance: "none",
        }}
      >
        {courses.map((c) => (
          <option key={c.id} value={String(c.id)}>
            {formatEventName(c.name, Boolean(c.is_relay))} · {eventTypeLabel(c.event_type)}
          </option>
        ))}
      </select>
    </label>
  );
}

function ImportBar({
  phase,
  progress,
  total,
  imported,
  skipped,
  message,
  heatIndex,
  heatsScrapingTotal,
  heatLabel,
}: {
  phase: string;
  progress: number;
  total: number;
  imported: number;
  skipped: number;
  message: string;
  heatIndex: number;
  heatsScrapingTotal: number;
  heatLabel: string;
}) {
  const pct = total > 0 ? Math.round((progress / total) * 100) : 0;
  // Fan-out Klikego (#156) : le backend émet un événement `scraping` par heat
  // avec `heat_index/heats_total/heat_label`. Sur un provider mono-course, ces
  // clés restent à zéro et on retombe sur le message initial.
  const fanoutProgress = heatsScrapingTotal > 0 && heatIndex > 0;
  const heatPct = fanoutProgress ? Math.round((heatIndex / heatsScrapingTotal) * 100) : 0;
  return (
    <div style={{ padding: "14px 18px", background: "var(--tcn-fill)", border: "1px solid var(--tcn-border)", borderRadius: "var(--tcn-radius-xl)" }}>
      {phase === "scraping" ? (
        fanoutProgress ? (
          <>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, color: "var(--tcn-text-body)", marginBottom: 8 }}>
              <span style={{ fontWeight: 600 }}>Récupération… épreuve {heatIndex}/{heatsScrapingTotal}</span>
              <span style={{ color: "var(--tcn-text-muted)" }}>{heatLabel}</span>
            </div>
            <div style={{ height: 8, background: "var(--tcn-surface)", borderRadius: 999, overflow: "hidden" }}>
              <div style={{ width: heatPct + "%", height: "100%", background: "var(--tcn-orange)", transition: "width var(--tcn-dur)" }} />
            </div>
          </>
        ) : (
          <div style={{ fontSize: 14, color: "var(--tcn-text-body)", fontWeight: 600 }}>{message || "Récupération des participants…"}</div>
        )
      ) : (
        <>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, color: "var(--tcn-text-body)", marginBottom: 8 }}>
            <span style={{ fontWeight: 600 }}>Import en cours… {progress}/{total}</span>
            <span style={{ color: "var(--tcn-text-muted)" }}>{imported} importés · {skipped} ignorés</span>
          </div>
          <div style={{ height: 8, background: "var(--tcn-surface)", borderRadius: 999, overflow: "hidden" }}>
            <div style={{ width: pct + "%", height: "100%", background: "var(--tcn-orange)", transition: "width var(--tcn-dur)" }} />
          </div>
        </>
      )}
    </div>
  );
}
