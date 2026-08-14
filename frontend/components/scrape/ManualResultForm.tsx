"use client";
import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { captureEvent } from "@/lib/posthog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  MANUAL_ENTRY_DISCIPLINES,
  MANUAL_ENTRY_DISCIPLINES_WITH_FORMAT,
  MANUAL_ENTRY_FORMATS,
  MANUAL_ENTRY_TIME_FIELDS,
} from "@/lib/constants";
import type { ScrapedPreview } from "@/lib/types";

const STATUTS = [
  { value: "finisher", label: "Terminée" },
  { value: "DNF", label: "Abandon" },
  { value: "DNS", label: "Forfait" },
];

const TIME_KEYS = ["swim_time", "t1_time", "bike_time", "t2_time", "run_time"] as const;

const schema = z
  .object({
    athlete_firstname: z.string().min(1, "Prénom requis"),
    athlete_name: z.string().min(1, "Nom requis"),
    event_date: z.string().min(1, "Date requise"),
    event_name: z.string().min(1, "Nom de l'épreuve requis"),
    discipline: z.string().min(1, "Discipline requise"),
    format: z.string().optional().default(""),
    format_label: z.string().optional().default(""),
    distance_km: z.string().optional().default(""),
    bib_number: z.string().optional().default(""),
    rank_overall: z.string().optional().default(""),
    individuel_ou_collectif: z.string().optional().default("individuel"),
    team_name: z.string().optional().default(""),
    status: z.string().optional().default("finisher"),
    evidence_url: z.string().optional().default(""),
    total_time: z.string().optional().default(""),
    swim_time: z.string().optional().default(""),
    t1_time: z.string().optional().default(""),
    bike_time: z.string().optional().default(""),
    t2_time: z.string().optional().default(""),
    run_time: z.string().optional().default(""),
  })
  .superRefine((data, ctx) => {
    if (data.format === "autre" && !data.format_label.trim()) {
      ctx.addIssue({
        code: "custom",
        path: ["format_label"],
        message: "Précision du format requise pour « Autre »",
      });
    }
    if (data.individuel_ou_collectif === "collectif" && !data.team_name.trim()) {
      ctx.addIssue({ code: "custom", path: ["team_name"], message: "Nom de l'équipe requis" });
    }
  });

/** `discipline-format` (`triathlon-m`), ou `discipline` nu si aucun format
 * normalisé n'a été choisi — la précision « Autre » vit hors slug, dans
 * `format_label` (cf. research.md D4). */
function computeEventType(discipline: string, format: string): string {
  if (!MANUAL_ENTRY_DISCIPLINES_WITH_FORMAT.has(discipline)) return discipline;
  if (!format || format === "autre") return discipline;
  return `${discipline}-${format}`;
}

export function ManualResultForm({
  defaultUrl = "",
  onSubmit,
  submitting,
}: {
  defaultUrl?: string;
  onSubmit: (data: Partial<ScrapedPreview>) => void;
  submitting?: boolean;
}) {
  // Drop explicit generic — comme dans l'ancienne version de ce fichier, le
  // désaccord Input/Output introduit par les `.default(...)` du schéma casse
  // le typage explicite ; laisser RHF l'inférer depuis le resolver.
  const {
    register,
    handleSubmit,
    control,
    formState: { errors },
  } = useForm({
    resolver: zodResolver(schema),
    defaultValues: {
      evidence_url: defaultUrl,
      individuel_ou_collectif: "individuel",
      status: "finisher",
    },
  });

  // `useWatch` plutôt que `watch()` : compatible avec le React Compiler
  // (`watch()` ne peut pas être mémoïsé en toute sécurité).
  const discipline = useWatch({ control, name: "discipline" });
  const format = useWatch({ control, name: "format" });
  const individuelOuCollectif = useWatch({ control, name: "individuel_ou_collectif" });

  const aUnFormat = MANUAL_ENTRY_DISCIPLINES_WITH_FORMAT.has(discipline);
  const champsTemps = MANUAL_ENTRY_TIME_FIELDS[discipline] ?? [];
  const clesTempsPertinentes = new Set(champsTemps.map((c) => c.key));

  return (
    <form
      className="grid gap-4 sm:grid-cols-2"
      onSubmit={handleSubmit((data) => {
        // Les temps devenus sans objet après un changement de discipline ne
        // doivent pas être transmis en silence (cas limite de la spec).
        const temps = Object.fromEntries(
          TIME_KEYS.map((key) => [key, clesTempsPertinentes.has(key) ? data[key] : ""]),
        );
        const estCollectif = data.individuel_ou_collectif === "collectif";
        const eventType = computeEventType(data.discipline, data.format);
        captureEvent("manual_result_submitted", { event_type: eventType });
        onSubmit({
          ...temps,
          provider: "manuel",
          athlete_firstname: data.athlete_firstname,
          athlete_name: data.athlete_name,
          event_date: data.event_date || null,
          event_name: data.event_name,
          event_type: eventType,
          format_label: data.format === "autre" ? data.format_label : "",
          distance_km: !aUnFormat && data.distance_km ? Number(data.distance_km) : null,
          bib_number: data.bib_number,
          rank_overall: data.rank_overall ? Number(data.rank_overall) : null,
          is_relay: estCollectif,
          team_name: estCollectif ? data.team_name : "",
          status: data.status,
          evidence_url: data.evidence_url,
          total_time: data.total_time,
        });
      })}
    >
      <Field label="Prénom" htmlFor="mrf-firstname" error={errors.athlete_firstname?.message}>
        <Input id="mrf-firstname" {...register("athlete_firstname")} />
      </Field>
      <Field label="Nom" htmlFor="mrf-name" error={errors.athlete_name?.message}>
        <Input id="mrf-name" {...register("athlete_name")} />
      </Field>
      <Field label="Date" htmlFor="mrf-date" error={errors.event_date?.message}>
        <Input id="mrf-date" type="date" {...register("event_date")} />
      </Field>
      <Field label="Nom de l'épreuve" htmlFor="mrf-event-name" error={errors.event_name?.message}>
        <Input id="mrf-event-name" {...register("event_name")} />
      </Field>

      <Field label="Discipline" htmlFor="mrf-discipline" error={errors.discipline?.message}>
        <select
          id="mrf-discipline"
          className="h-9 rounded-md border bg-background px-2"
          {...register("discipline")}
        >
          <option value="">—</option>
          {MANUAL_ENTRY_DISCIPLINES.map((d) => (
            <option key={d.value} value={d.value}>{d.label}</option>
          ))}
        </select>
      </Field>

      {aUnFormat ? (
        <Field label="Format" htmlFor="mrf-format">
          <select
            id="mrf-format"
            className="h-9 rounded-md border bg-background px-2"
            {...register("format")}
          >
            <option value="">—</option>
            {MANUAL_ENTRY_FORMATS.map((f) => (
              <option key={f.value} value={f.value}>{f.label}</option>
            ))}
          </select>
        </Field>
      ) : (
        <Field label="Distance totale (km)" htmlFor="mrf-distance-km">
          <Input id="mrf-distance-km" type="number" step="0.1" {...register("distance_km")} />
        </Field>
      )}

      {format === "autre" && (
        <Field
          label="Précision du format"
          htmlFor="mrf-format-label"
          error={errors.format_label?.message}
        >
          <Input id="mrf-format-label" {...register("format_label")} />
        </Field>
      )}

      <Field label="Dossard" htmlFor="mrf-bib"><Input id="mrf-bib" {...register("bib_number")} /></Field>
      <Field label="Place générale" htmlFor="mrf-rank">
        <Input id="mrf-rank" type="number" {...register("rank_overall")} />
      </Field>

      <fieldset className="flex flex-col gap-1 sm:col-span-2">
        <legend className="text-sm font-medium">Individuel ou collectif</legend>
        <div className="flex gap-4">
          <label className="flex items-center gap-2">
            <input
              type="radio"
              value="individuel"
              {...register("individuel_ou_collectif")}
            />
            Individuel
          </label>
          <label className="flex items-center gap-2">
            <input
              type="radio"
              value="collectif"
              {...register("individuel_ou_collectif")}
            />
            Collectif
          </label>
        </div>
      </fieldset>

      {individuelOuCollectif === "collectif" && (
        <Field
          label="Nom de l'équipe"
          htmlFor="mrf-team-name"
          error={errors.team_name?.message}
        >
          <Input id="mrf-team-name" {...register("team_name")} />
        </Field>
      )}

      <Field label="Statut" htmlFor="mrf-status">
        <select
          id="mrf-status"
          className="h-9 rounded-md border bg-background px-2"
          {...register("status")}
        >
          {STATUTS.map((s) => (
            <option key={s.value} value={s.value}>{s.label}</option>
          ))}
        </select>
      </Field>

      <Field label="Lien vers les résultats" htmlFor="mrf-evidence-url">
        <Input id="mrf-evidence-url" {...register("evidence_url")} />
      </Field>

      <fieldset className="grid gap-4 sm:col-span-2 sm:grid-cols-2 border rounded-md p-3">
        <legend className="text-sm font-medium px-1">Temps</legend>
        <Field label="Temps total" htmlFor="mrf-total-time">
          <Input id="mrf-total-time" placeholder="HH:MM:SS" {...register("total_time")} />
        </Field>
        {champsTemps.map((c) => (
          <Field key={c.key} label={c.label} htmlFor={`mrf-${c.key}`}>
            <Input id={`mrf-${c.key}`} placeholder="HH:MM:SS" {...register(c.key)} />
          </Field>
        ))}
      </fieldset>

      <div className="sm:col-span-2">
        <Button type="submit" disabled={submitting}>
          {submitting ? "Enregistrement…" : "Enregistrer le résultat"}
        </Button>
      </div>
    </form>
  );
}

function Field({
  label,
  htmlFor,
  error,
  children,
}: {
  label: string;
  htmlFor: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1">
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
      {error && (
        <span role="alert" className="text-xs text-destructive">
          {error}
        </span>
      )}
    </div>
  );
}
