"use client";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { EVENT_TYPE_OPTIONS } from "@/lib/constants";
import type { ScrapedPreview } from "@/lib/types";

const schema = z.object({
  athlete_firstname: z.string().min(1, "Prénom requis"),
  athlete_name: z.string().min(1, "Nom requis"),
  gender: z.string().optional().default(""),
  club: z.string().optional().default(""),
  event_name: z.string().min(1, "Épreuve requise"),
  event_date: z.string().optional().default(""),
  event_type: z.string().min(1, "Type requis"),
  bib_number: z.string().optional().default(""),
  category: z.string().optional().default(""),
  total_time: z.string().optional().default(""),
  swim_time: z.string().optional().default(""),
  t1_time: z.string().optional().default(""),
  bike_time: z.string().optional().default(""),
  t2_time: z.string().optional().default(""),
  run_time: z.string().optional().default(""),
  source_url: z.string().optional().default(""),
});

export function ManualResultForm({
  defaultUrl = "",
  onSubmit,
  submitting,
}: {
  defaultUrl?: string;
  onSubmit: (data: Partial<ScrapedPreview>) => void;
  submitting?: boolean;
}) {
  // Drop explicit generic — let RHF infer Input/Output from the zod v4 resolver
  // to avoid the input/output type mismatch caused by .default("") fields.
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm({
    resolver: zodResolver(schema),
    defaultValues: { source_url: defaultUrl },
  });

  return (
    <form
      className="grid gap-4 sm:grid-cols-2"
      onSubmit={handleSubmit((data) =>
        onSubmit({ ...data, provider: "manuel", event_date: data.event_date || null }),
      )}
    >
      <Field label="Prénom" error={errors.athlete_firstname?.message}>
        <Input {...register("athlete_firstname")} />
      </Field>
      <Field label="Nom" error={errors.athlete_name?.message}>
        <Input {...register("athlete_name")} />
      </Field>
      <Field label="Genre"><Input {...register("gender")} placeholder="M / F" /></Field>
      <Field label="Club"><Input {...register("club")} /></Field>
      <Field label="Épreuve" error={errors.event_name?.message}>
        <Input {...register("event_name")} />
      </Field>
      <Field label="Date"><Input type="date" {...register("event_date")} /></Field>
      <Field label="Type d'épreuve" error={errors.event_type?.message}>
        <select className="h-9 rounded-md border bg-background px-2" {...register("event_type")}>
          <option value="">—</option>
          {EVENT_TYPE_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </Field>
      <Field label="Dossard"><Input {...register("bib_number")} /></Field>
      <Field label="Catégorie"><Input {...register("category")} /></Field>
      <Field label="Temps total"><Input {...register("total_time")} placeholder="HH:MM:SS" /></Field>
      <Field label="Natation"><Input {...register("swim_time")} placeholder="HH:MM:SS" /></Field>
      <Field label="T1"><Input {...register("t1_time")} /></Field>
      <Field label="Vélo"><Input {...register("bike_time")} /></Field>
      <Field label="T2"><Input {...register("t2_time")} /></Field>
      <Field label="Course"><Input {...register("run_time")} /></Field>
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
  error,
  children,
}: {
  label: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1">
      <Label>{label}</Label>
      {children}
      {error && <span className="text-xs text-destructive">{error}</span>}
    </div>
  );
}
