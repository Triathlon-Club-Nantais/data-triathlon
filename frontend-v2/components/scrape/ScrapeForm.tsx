"use client";
import { useState, useCallback, useEffect, useRef } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { apiClient } from "@/lib/api/client";
import { useSaveParticipation } from "@/lib/queries/participations";
import { useImportStream } from "@/hooks/useImportStream";
import { ProviderDetector } from "./ProviderDetector";
import { ImportProgress } from "./ImportProgress";
import { ManualResultForm } from "./ManualResultForm";
import type { ScrapedPreview } from "@/lib/types";

export function ScrapeForm() {
  const [url, setUrl] = useState("");
  const [manual, setManual] = useState(false);
  // Garde anti double-signalement pour une même URL en échec.
  const reportedRef = useRef<string | null>(null);

  const save = useSaveParticipation();
  const importStream = useImportStream();
  const { phase, error, running } = importStream.state;

  const startImport = useCallback(() => {
    reportedRef.current = null;
    setManual(false);
    importStream.start(url);
  }, [url, importStream.start]);

  // Option A : sur échec réel de l'import, signaler le fournisseur et proposer la saisie manuelle.
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

  return (
    <div className="space-y-6">
      <Card>
        <CardContent className="space-y-4">
          <StepHeader n={1} title="Source" hint="URL de chronométrage de l'épreuve" />
          <div className="flex flex-col gap-1.5">
            <Label>URL de chronométrage</Label>
            <Input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://…"
            />
            <ProviderDetector url={url} />
          </div>
          <div className="flex flex-wrap items-end gap-3">
            <Button onClick={startImport} disabled={!url || running}>
              {running ? "Import…" : "Importer l'épreuve"}
            </Button>
            <Button variant="outline" onClick={() => setManual((m) => !m)}>
              Saisie manuelle
            </Button>
          </div>
        </CardContent>
      </Card>

      {manual && (
        <Card>
          <CardContent className="space-y-4">
            <StepHeader n={2} title="Saisie manuelle" hint="Renseignez le résultat à la main" />
            <ManualResultForm defaultUrl={url} onSubmit={persist} submitting={save.isPending} />
          </CardContent>
        </Card>
      )}

      <ImportProgress state={importStream.state} />
    </div>
  );
}

function StepHeader({ n, title, hint }: { n: number; title: string; hint: string }) {
  return (
    <div className="flex items-center gap-3 border-b pb-3">
      <span className="grid size-7 shrink-0 place-content-center rounded-full bg-primary text-primary-foreground text-sm font-bold">
        {n}
      </span>
      <div>
        <h3 className="font-heading font-semibold leading-tight">{title}</h3>
        <p className="text-xs text-muted-foreground">{hint}</p>
      </div>
    </div>
  );
}
