"use client";
import { useState, useCallback } from "react";
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
  const [bib, setBib] = useState("");
  const [preview, setPreview] = useState<ScrapedPreview | null>(null);
  const [scraping, setScraping] = useState(false);
  const [manual, setManual] = useState(false);

  const save = useSaveParticipation();
  const importStream = useImportStream();

  const scrape = useCallback(async () => {
    setScraping(true);
    setManual(false);
    try {
      const result = await apiClient.scrape(url, bib || null);
      setPreview(result);
    } catch (e) {
      toast.error((e as Error).message);
      setManual(true);
      apiClient.reportPendingProvider(url).catch(() => {});
    } finally {
      setScraping(false);
    }
  }, [url, bib]);

  const persist = useCallback(
    async (data: Partial<ScrapedPreview>) => {
      try {
        await save.mutateAsync(data);
        toast.success("Résultat enregistré.");
        setPreview(null);
        const eventUrl = data.source_url || url;
        if (eventUrl) importStream.start(eventUrl);
      } catch (e) {
        toast.error((e as Error).message);
      }
    },
    [save, url, importStream],
  );

  return (
    <div className="space-y-6">
      <Card>
        <CardContent className="space-y-4 p-5">
          <div className="flex flex-col gap-1">
            <Label>URL de chronométrage</Label>
            <Input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://…"
            />
            <ProviderDetector url={url} />
          </div>
          <div className="flex items-end gap-3">
            <div className="flex flex-col gap-1">
              <Label>Dossard (optionnel)</Label>
              <Input value={bib} onChange={(e) => setBib(e.target.value)} className="w-32" />
            </div>
            <Button onClick={scrape} disabled={!url || scraping}>
              {scraping ? "Analyse…" : "Analyser"}
            </Button>
            <Button variant="outline" onClick={() => setManual((m) => !m)}>
              Saisie manuelle
            </Button>
          </div>
        </CardContent>
      </Card>

      {preview && !manual && (
        <Card>
          <CardContent className="space-y-4 p-5">
            <h3 className="font-semibold">Prévisualisation — vérifiez puis enregistrez</h3>
            <PreviewEditor preview={preview} onChange={setPreview} />
            <Button onClick={() => persist(preview)} disabled={save.isPending}>
              {save.isPending ? "Enregistrement…" : "Enregistrer"}
            </Button>
          </CardContent>
        </Card>
      )}

      {manual && (
        <Card>
          <CardContent className="space-y-4 p-5">
            <h3 className="font-semibold">Saisie manuelle</h3>
            <ManualResultForm defaultUrl={url} onSubmit={persist} submitting={save.isPending} />
          </CardContent>
        </Card>
      )}

      <ImportProgress state={importStream.state} />
    </div>
  );
}

/** Éditeur minimal des champs clés de la preview avant enregistrement. */
function PreviewEditor({
  preview,
  onChange,
}: {
  preview: ScrapedPreview;
  onChange: (p: ScrapedPreview) => void;
}) {
  const set = (k: keyof ScrapedPreview, v: string) => onChange({ ...preview, [k]: v });
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <Labeled label="Prénom"><Input value={preview.athlete_firstname} onChange={(e) => set("athlete_firstname", e.target.value)} /></Labeled>
      <Labeled label="Nom"><Input value={preview.athlete_name} onChange={(e) => set("athlete_name", e.target.value)} /></Labeled>
      <Labeled label="Club"><Input value={preview.club} onChange={(e) => set("club", e.target.value)} /></Labeled>
      <Labeled label="Catégorie"><Input value={preview.category} onChange={(e) => set("category", e.target.value)} /></Labeled>
      <Labeled label="Épreuve"><Input value={preview.event_name} onChange={(e) => set("event_name", e.target.value)} /></Labeled>
      <Labeled label="Temps total"><Input value={preview.total_time} onChange={(e) => set("total_time", e.target.value)} /></Labeled>
    </div>
  );
}

function Labeled({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <Label>{label}</Label>
      {children}
    </div>
  );
}
