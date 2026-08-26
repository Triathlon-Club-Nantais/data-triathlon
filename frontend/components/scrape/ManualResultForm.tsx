"use client";
import { useEffect } from "react";
import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

// #570 — `zod` sonde `new Function("")` au premier `parse` pour activer sa
// compilation JIT. Sous CSP stricte le navigateur **rapporte la sonde en
// violation `script-src eval`** alors même que zod rattrape le throw : la
// validation marche, la console crie. `jitless` court-circuite la sonde, et ne
// coûte rien — sans `'unsafe-eval'`, le JIT n'aurait de toute façon jamais
// servi (`node_modules/zod/v4/core/util.cjs`, `allowsEval`).
z.config({ jitless: true });
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
import type { FieldError } from "@/lib/api/client";
import { participationStatusLabel } from "@/lib/labels";

// `DSQ` reste hors de la saisie manuelle (#1084, hors périmètre).
const STATUTS = (["finisher", "DNF", "DNS"] as const).map((value) => ({
  value,
  label: participationStatusLabel(value),
}));

const TIME_KEYS = ["swim_time", "t1_time", "bike_time", "t2_time", "run_time"] as const;

// Les règles de `POST /participations` depuis #1019, vérifiées avant l'envoi :
// le serveur les rendrait en 422, en anglais pour les types génériques.
const DUREE = /^(\d{1,3}:[0-5]\d:[0-5]\d)?$/;
const MESSAGE_DUREE = "Format attendu H:MM:SS (par exemple 1:05:30).";
const MESSAGE_PLACE = "La place doit être un entier supérieur ou égal à 1.";
const duree = z.string().trim().regex(DUREE, MESSAGE_DUREE).optional().default("");
const texte = z.string().trim().optional().default("");

/** Le refus d'un champ par le serveur, en français : les types génériques de
 *  Pydantic arrivent en anglais, un validateur maison en français. */
const MESSAGE_SERVEUR: Record<string, string> = {
  string_pattern_mismatch: MESSAGE_DUREE,
  date_from_datetime_parsing: "Date invalide.",
  date_parsing: "Date invalide.",
  date_type: "Date invalide.",
  string_too_short: "Champ requis.",
  missing: "Champ requis.",
  greater_than_equal: MESSAGE_PLACE,
  literal_error: "Valeur hors de la liste proposée.",
};

/** Le champ du formulaire qui porte un champ de l'API. */
const CHAMP_DU_FORMULAIRE: Record<string, string> = { event_type: "discipline" };

const schema = z
  .object({
    athlete_firstname: z.string().trim().min(1, "Prénom requis"),
    athlete_name: z.string().trim().min(1, "Nom requis"),
    event_date: z
      .string()
      .min(1, "Date requise")
      .regex(/^\d{4}-\d{2}-\d{2}$/, "Date invalide."),
    event_name: z.string().trim().min(1, "Nom de l'épreuve requis"),
    discipline: z.string().min(1, "Discipline requise"),
    format: z.string().optional().default(""),
    format_label: texte,
    distance_km: z.string().optional().default(""),
    bib_number: texte,
    rank_overall: z
      .string()
      .trim()
      .refine((v) => v === "" || (/^\d+$/.test(v) && Number(v) >= 1), MESSAGE_PLACE)
      .optional()
      .default(""),
    individuel_ou_collectif: z.string().optional().default("individuel"),
    team_name: texte,
    status: z.enum(["finisher", "DNF", "DNS"]).optional().default("finisher"),
    evidence_url: texte,
    total_time: duree,
    swim_time: duree,
    t1_time: duree,
    bike_time: duree,
    t2_time: duree,
    run_time: duree,
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

const GROUPE = "grid gap-4 sm:grid-cols-2";

export function ManualResultForm({
  defaultUrl = "",
  onSubmit,
  submitting,
  serverErrors,
}: {
  defaultUrl?: string;
  onSubmit: (data: Partial<ScrapedPreview>) => void;
  submitting?: boolean;
  /** Refus par champ d'un 422 que la validation locale n'a pas vu venir (#1019). */
  serverErrors?: Record<string, FieldError>;
}) {
  // Drop explicit generic — comme dans l'ancienne version de ce fichier, le
  // désaccord Input/Output introduit par les `.default(...)` du schéma casse
  // le typage explicite ; laisser RHF l'inférer depuis le resolver.
  const {
    register,
    handleSubmit,
    control,
    setError,
    formState: { errors },
  } = useForm({
    resolver: zodResolver(schema),
    // Chaque champ se corrige là où il se remplit (ACT-11) : sans `mode`, RHF
    // ne valide qu'à la soumission et les manques n'arrivent qu'au bas de page,
    // tous d'un coup. `onTouched` et non `onChange` : signaler « Prénom requis »
    // à la première lettre tapée est du bruit, pas une aide.
    mode: "onTouched",
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

  useEffect(() => {
    for (const [champ, refus] of Object.entries(serverErrors ?? {})) {
      const cible = CHAMP_DU_FORMULAIRE[champ] ?? champ;
      if (!(cible in schema.shape)) continue;
      setError(cible as keyof z.input<typeof schema>, {
        type: "server",
        message: MESSAGE_SERVEUR[refus.type] ?? refus.message,
      });
    }
  }, [serverErrors, setError]);

  const aUnFormat = MANUAL_ENTRY_DISCIPLINES_WITH_FORMAT.has(discipline);
  const champsTemps = MANUAL_ENTRY_TIME_FIELDS[discipline] ?? [];
  const clesTempsPertinentes = new Set(champsTemps.map((c) => c.key));

  return (
    <form
      className="flex flex-col gap-6"
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
      {/* Un astérisque rouge est une convention pour qui la connaît déjà : la
          légende la pose, avant le premier champ qui la porte. */}
      <p className="text-sm text-muted-foreground">
        Les champs marqués <span className="text-[var(--tcn-danger-text)]">*</span> sont
        obligatoires.
      </p>

      <Groupe titre="Qui">
        <Field label="Prénom" htmlFor="mrf-firstname" required error={errors.athlete_firstname?.message}>
          <Input id="mrf-firstname" aria-required="true" {...register("athlete_firstname")} />
        </Field>
        <Field label="Nom" htmlFor="mrf-name" required error={errors.athlete_name?.message}>
          <Input id="mrf-name" aria-required="true" {...register("athlete_name")} />
        </Field>
      </Groupe>

      <Groupe titre="Quelle épreuve">
        <Field label="Date" htmlFor="mrf-date" required error={errors.event_date?.message}>
          <Input id="mrf-date" type="date" aria-required="true" {...register("event_date")} />
        </Field>
        <Field
          label="Nom de l'épreuve"
          htmlFor="mrf-event-name"
          required
          error={errors.event_name?.message}
        >
          <Input id="mrf-event-name" aria-required="true" {...register("event_name")} />
        </Field>

        <Field label="Discipline" htmlFor="mrf-discipline" required error={errors.discipline?.message}>
          <select
            id="mrf-discipline"
            aria-required="true"
            className="tcn-input h-9 rounded-md border bg-background px-2"
            {...register("discipline")}
          >
            <option value="">—</option>
            {MANUAL_ENTRY_DISCIPLINES.map((d) => (
              <option key={d.value} value={d.value}>{d.label}</option>
            ))}
          </select>
        </Field>

        {aUnFormat ? (
          <Field label="Format" htmlFor="mrf-format" optional>
            <select
              id="mrf-format"
              className="tcn-input h-9 rounded-md border bg-background px-2"
              {...register("format")}
            >
              <option value="">—</option>
              {MANUAL_ENTRY_FORMATS.map((f) => (
                <option key={f.value} value={f.value}>{f.label}</option>
              ))}
            </select>
          </Field>
        ) : (
          <Field label="Distance totale (km)" htmlFor="mrf-distance-km" optional>
            <Input id="mrf-distance-km" type="number" step="0.1" {...register("distance_km")} />
          </Field>
        )}

        {format === "autre" && (
          <Field
            label="Précision du format"
            htmlFor="mrf-format-label"
            required
            error={errors.format_label?.message}
          >
            <Input id="mrf-format-label" aria-required="true" {...register("format_label")} />
          </Field>
        )}
      </Groupe>

      <Groupe titre="Quel résultat">
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
            required
            error={errors.team_name?.message}
          >
            <Input id="mrf-team-name" aria-required="true" {...register("team_name")} />
          </Field>
        )}

        <Field label="Statut" htmlFor="mrf-status">
          <select
            id="mrf-status"
            className="tcn-input h-9 rounded-md border bg-background px-2"
            {...register("status")}
          >
            {STATUTS.map((s) => (
              <option key={s.value} value={s.value}>{s.label}</option>
            ))}
          </select>
        </Field>

        <Field label="Dossard" htmlFor="mrf-bib" optional>
          <Input id="mrf-bib" {...register("bib_number")} />
        </Field>
        <Field label="Place générale" htmlFor="mrf-rank" optional error={errors.rank_overall?.message}>
          <Input id="mrf-rank" type="number" {...register("rank_overall")} />
        </Field>

        <Field
          label="Lien vers la page de résultats, si vous en avez un"
          htmlFor="mrf-evidence-url"
          optional
        >
          <Input id="mrf-evidence-url" {...register("evidence_url")} />
        </Field>
      </Groupe>

      <Groupe titre="Temps">
        <Field label="Temps total" htmlFor="mrf-total-time" optional error={errors.total_time?.message}>
          <Input id="mrf-total-time" placeholder="HH:MM:SS" {...register("total_time")} />
        </Field>
        {champsTemps.length > 0 && (
          // Cinq champs de plus que personne n'a sous la main au moment de
          // saisir : repliés, ils ne pèsent plus sur la décision de commencer.
          // Ouverts d'office sur une erreur : un message replié ne se lit pas.
          <details
            className="sm:col-span-2"
            open={champsTemps.some((c) => errors[c.key]) || undefined}
          >
            {/* `min-h-11` : 44 px, le seuil de cible tactile que le dépôt s'est
                donné sur `.tcn-btn` — c'est la commande qui ouvre les cinq
                champs, sur un écran pensé mobile d'abord. */}
            <summary className="flex min-h-11 cursor-pointer items-center text-sm font-medium">
              Ajouter vos temps par discipline
            </summary>
            <div className={`${GROUPE} pt-2`}>
              {champsTemps.map((c) => (
                <Field
                  key={c.key}
                  label={c.label}
                  htmlFor={`mrf-${c.key}`}
                  optional
                  error={errors[c.key]?.message}
                >
                  <Input id={`mrf-${c.key}`} placeholder="HH:MM:SS" {...register(c.key)} />
                </Field>
              ))}
            </div>
          </details>
        )}
      </Groupe>

      <div>
        <Button type="submit" disabled={submitting}>
          {submitting ? "Enregistrement…" : "Enregistrer votre participation"}
        </Button>
      </div>
    </form>
  );
}

function Groupe({ titre, children }: { titre: string; children: React.ReactNode }) {
  return (
    <fieldset className={GROUPE}>
      {/* Pas de `col-span` ici : un `<legend>` rendu est sorti du flux interne
          du `<fieldset>`, il n'est donc jamais un élément de la grille — d'où
          aussi la marge basse, que le `gap` ne lui applique pas. */}
      <legend className="mb-3 text-base font-semibold text-[var(--tcn-ink)]">{titre}</legend>
      {children}
    </fieldset>
  );
}

function Field({
  label,
  htmlFor,
  error,
  required,
  optional,
  children,
}: {
  label: string;
  htmlFor: string;
  error?: string;
  required?: boolean;
  optional?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1">
      <span className="flex items-center gap-1">
        <Label htmlFor={htmlFor}>
          {label}
          {optional && (
            <span className="font-normal text-muted-foreground">{" (optionnel)"}</span>
          )}
        </Label>
        {/* Hors du `<Label>` : l'astérisque est décoratif — `aria-required` porte
            l'information sur le champ — et le laisser dedans collerait un « * »
            au libellé, donc au nom accessible. */}
        {required && (
          <span aria-hidden="true" className="text-sm text-destructive">
            *
          </span>
        )}
      </span>
      {children}
      {error && (
        <span role="alert" className="text-xs text-[var(--tcn-danger-text)]">
          {error}
        </span>
      )}
    </div>
  );
}
