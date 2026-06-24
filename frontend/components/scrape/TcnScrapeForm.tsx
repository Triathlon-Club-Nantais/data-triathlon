"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Card, Input, Button, Alert } from "@/components/tcn";
import { apiClient } from "@/lib/api/client";
import { useSaveParticipation } from "@/lib/queries/participations";
import { useImportStream } from "@/hooks/useImportStream";
import { ProviderDetector } from "./ProviderDetector";
import { ManualResultForm } from "./ManualResultForm";
import type { ScrapedPreview } from "@/lib/types";

export function TcnScrapeForm() {
  const [url, setUrl] = useState("");
  const [manual, setManual] = useState(false);
  const reportedRef = useRef<string | null>(null);

  const save = useSaveParticipation();
  const importStream = useImportStream();
  const { phase, error, running, imported, skipped, total, progress, cached, message } = importStream.state;

  const submit = useCallback(() => {
    const v = url.trim();
    if (!v || running) return;
    reportedRef.current = null;
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

  const isDuplicate = phase === "done" && (cached || (imported === 0 && skipped > 0));
  const inputStatus = isDuplicate ? "error" : phase === "error" ? "warning" : running ? "active" : "default";

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
            />
            <div style={{ marginTop: 8 }}>
              <ProviderDetector url={url} />
            </div>
          </div>
          <Button size="lg" onClick={submit} disabled={running} iconRight={<span>→</span>} style={{ borderRadius: "var(--tcn-radius-xl)" }}>
            {running ? "Import en cours…" : "Enregistrer les résultats"}
          </Button>
        </div>

        {(phase === "scraping" || phase === "saving") && (
          <div style={{ marginTop: 14 }}>
            <ImportBar phase={phase} progress={progress} total={total} imported={imported} skipped={skipped} message={message} />
          </div>
        )}

        {phase === "done" && !isDuplicate && (
          <div style={{ marginTop: 14 }}>
            <Alert status="success" title="Résultats enregistrés avec succès !">
              {imported} résultat{imported > 1 ? "s" : ""} ajouté{imported > 1 ? "s" : ""}
              {skipped > 0 ? ` · ${skipped} déjà présent${skipped > 1 ? "s" : ""}` : ""}. Les statistiques du club ont été mises à jour.
            </Alert>
          </div>
        )}
        {isDuplicate && (
          <div style={{ marginTop: 14 }}>
            <Alert status="error" title="Résultats déjà enregistrés">
              Ces résultats ont déjà été ajoutés. Les statistiques sont à jour ({skipped} participants en base).
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

function ImportBar({
  phase,
  progress,
  total,
  imported,
  skipped,
  message,
}: {
  phase: string;
  progress: number;
  total: number;
  imported: number;
  skipped: number;
  message: string;
}) {
  const pct = total > 0 ? Math.round((progress / total) * 100) : 0;
  return (
    <div style={{ padding: "14px 18px", background: "var(--tcn-fill)", border: "1px solid var(--tcn-border)", borderRadius: "var(--tcn-radius-xl)" }}>
      {phase === "scraping" ? (
        <div style={{ fontSize: 14, color: "var(--tcn-text-body)", fontWeight: 600 }}>{message || "Récupération des participants…"}</div>
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
