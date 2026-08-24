"use client";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { useDebounce } from "@/hooks/useDebounce";
import { X } from "lucide-react";
import { captureEvent } from "@/lib/posthog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Card, CardContent } from "@/components/ui/card";
import { Sheet, SheetClose, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { SlidersHorizontal } from "lucide-react";
import { EVENT_TYPE_OPTIONS, eventTypeLabel } from "@/lib/constants";
import { formatDate } from "@/lib/utils/date";

export function buildResultsQuery(filters: Record<string, string | undefined>): string {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([k, v]) => {
    if (v && v !== "") params.set(k, v);
  });
  return params.toString();
}

const ALL = "all";

export function ResultsFilters() {
  const router = useRouter();
  const sp = useSearchParams();
  const [name, setName] = useState(sp.get("name") ?? "");
  const [eventName, setEventName] = useState(sp.get("event_name") ?? "");
  const [eventType, setEventType] = useState(sp.get("event_type") ?? "");
  const [dateFrom, setDateFrom] = useState(sp.get("date_from") ?? "");
  const [dateTo, setDateTo] = useState(sp.get("date_to") ?? "");
  const [volet, setVolet] = useState(false);

  // Compte des filtres **repliés** actifs, athlète exclu : il reste visible
  // hors du volet, le compter ferait mentir le bouton.
  const nbReplies = ["event_name", "event_type", "date_from", "date_to"].filter((cle) =>
    sp.get(cle),
  ).length;

  const scope = sp.get("scope") ?? undefined;
  const sort = sp.get("sort") ?? undefined;

  function urlFor(filters: Record<string, string | undefined>) {
    const qs = buildResultsQuery({ ...filters, scope, sort });
    return `/resultats${qs ? `?${qs}` : ""}`;
  }

  function push(filters: Record<string, string | undefined>) {
    router.push(urlFor(filters));
  }

  function apply() {
    const activeFilters = Object.fromEntries(
      Object.entries({ name, event_name: eventName, event_type: eventType, date_from: dateFrom, date_to: dateTo })
        .filter(([, v]) => v !== ""),
    );
    captureEvent("results_filter_applied", {
      filter_count: Object.keys(activeFilters).length,
      has_athlete_filter: !!name,
      has_event_name_filter: !!eventName,
      has_event_type_filter: !!eventType,
      has_date_filter: !!(dateFrom || dateTo),
    });
    push({
      name,
      event_name: eventName,
      event_type: eventType,
      date_from: dateFrom,
      date_to: dateTo,
    });
  }

  // Recherche live : les champs texte filtrent dès la frappe (#383), sans
  // attendre Entrée ou le bouton "Filtrer". Le debounce évite un appel par
  // caractère ; on saute le premier rendu et les cas déjà à jour dans l'URL.
  // `replace` (pas `push`) : sinon chaque groupe de frappe empile une entrée
  // d'historique et le bouton Retour ne fait que rejouer la saisie.
  // Discipline/dates viennent de l'URL (déjà appliqués), pas de l'état local :
  // sinon un changement de discipline ou de date non validé par "Filtrer"
  // serait appliqué en douce dès qu'on tape dans un champ texte (#387).
  const debouncedName = useDebounce(name);
  const debouncedEventName = useDebounce(eventName);
  useEffect(() => {
    if (
      debouncedName === (sp.get("name") ?? "") &&
      debouncedEventName === (sp.get("event_name") ?? "")
    ) {
      return;
    }
    router.replace(
      urlFor({
        name: debouncedName,
        event_name: debouncedEventName,
        event_type: sp.get("event_type") ?? "",
        date_from: sp.get("date_from") ?? "",
        date_to: sp.get("date_to") ?? "",
      }),
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedName, debouncedEventName]);

  function reset() {
    setName("");
    setEventName("");
    setEventType("");
    setDateFrom("");
    setDateTo("");
    push({});
  }

  // Réinitialisation **partielle** : seuls les quatre champs repliés dans le
  // volet, l'athlète restant hors de son périmètre (#M2 revue finale).
  function resetVolet() {
    setEventName("");
    setEventType("");
    setDateFrom("");
    setDateTo("");
    push({ name, event_name: "", event_type: "", date_from: "", date_to: "" });
  }

  // Referme la fuite #387 côté volet : sorti sans valider (Échap, clic sur le
  // fond), l'état local des quatre champs repliés reste modifié tant qu'on ne
  // le remet pas à ce que l'URL dit déjà appliqué — sinon une saisie abandonnée
  // s'applique au prochain Entrée dans « Athlète », et réapparaît comme active
  // si l'on rouvre le volet.
  function resetVoletDepuisUrl() {
    setEventName(sp.get("event_name") ?? "");
    setEventType(sp.get("event_type") ?? "");
    setDateFrom(sp.get("date_from") ?? "");
    setDateTo(sp.get("date_to") ?? "");
  }

  // Filtres actifs (depuis l'URL) → chips.
  const active: { key: string; label: string }[] = [];
  if (sp.get("name")) active.push({ key: "name", label: `Athlète : ${sp.get("name")}` });
  if (sp.get("event_name"))
    active.push({ key: "event_name", label: `Épreuve : ${sp.get("event_name")}` });
  if (sp.get("event_type"))
    active.push({ key: "event_type", label: eventTypeLabel(sp.get("event_type")) });
  if (sp.get("date_from"))
    active.push({ key: "date_from", label: `Du ${formatDate(sp.get("date_from"))}` });
  if (sp.get("date_to"))
    active.push({ key: "date_to", label: `Au ${formatDate(sp.get("date_to"))}` });

  function removeChip(key: string) {
    const next = {
      name: sp.get("name") ?? undefined,
      event_name: sp.get("event_name") ?? undefined,
      event_type: sp.get("event_type") ?? undefined,
      date_from: sp.get("date_from") ?? undefined,
      date_to: sp.get("date_to") ?? undefined,
    } as Record<string, string | undefined>;
    next[key] = undefined;
    setName(next.name ?? "");
    setEventName(next.event_name ?? "");
    setEventType(next.event_type ?? "");
    setDateFrom(next.date_from ?? "");
    setDateTo(next.date_to ?? "");
    push(next);
  }

  return (
    <Card>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap items-end gap-3">
          <Field id="filtre-athlete" label="Athlète">
            <Input
              id="filtre-athlete"
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && apply()}
              placeholder="Rechercher un athlète"
              className="w-full sm:w-48"
            />
          </Field>
          <div className="hidden sm:contents">
            <ChampsReplies
              suffixe="inline"
              eventName={eventName}
              setEventName={setEventName}
              eventType={eventType}
              setEventType={setEventType}
              dateFrom={dateFrom}
              setDateFrom={setDateFrom}
              dateTo={dateTo}
              setDateTo={setDateTo}
              onValider={apply}
            />
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              className="sm:hidden"
              aria-expanded={volet}
              aria-haspopup="dialog"
              onClick={() => setVolet(true)}
            >
              <SlidersHorizontal className="size-4" />
              {nbReplies > 0 ? `Filtres (${nbReplies})` : "Filtres"}
            </Button>
            {/* « Filtrer » ne sert plus sous `sm` : le champ athlète y filtre en
                direct (#383) et le volet porte le même verbe (#485). */}
            <Button className="hidden sm:inline-flex" onClick={apply}>
              Filtrer
            </Button>
            {active.length > 0 && (
              <Button variant="ghost" className="hidden sm:inline-flex" onClick={reset}>
                Réinitialiser
              </Button>
            )}
          </div>
        </div>

        {active.length > 0 && (
          <div className="flex flex-wrap gap-2 border-t pt-3">
            {active.map((chip) => (
              // `h-7` (28 px) : le badge grandit avec la croix — sans quoi
              // `overflow-hidden` (badge, `h-5` par défaut) la retaillerait à
              // sa taille d'origine, 16 px (#479).
              <Badge key={chip.key} variant="secondary" className="h-7 gap-1 pr-1">
                {chip.label}
                <Button
                  size="icon-xs"
                  variant="ghost"
                  className="rounded-full p-0"
                  onClick={() => removeChip(chip.key)}
                  aria-label={`Retirer ${chip.label}`}
                >
                  <X className="size-3" />
                </Button>
              </Badge>
            ))}
          </div>
        )}

        <Sheet
          open={volet}
          onOpenChange={(open) => {
            setVolet(open);
            if (!open) resetVoletDepuisUrl();
          }}
        >
          <SheetContent side="right" className="w-80 overflow-y-auto">
            <div className="flex items-center justify-between">
              <SheetTitle>Filtres</SheetTitle>
              <SheetClose
                aria-label="Fermer les filtres"
                className="rounded-full p-1 text-[var(--tcn-text-faint)] hover:text-[var(--tcn-ink)]"
              >
                <X className="size-4" />
              </SheetClose>
            </div>
            <div className="flex flex-col gap-3">
              <ChampsReplies
                suffixe="volet"
                eventName={eventName}
                setEventName={setEventName}
                eventType={eventType}
                setEventType={setEventType}
                dateFrom={dateFrom}
                setDateFrom={setDateFrom}
                dateTo={dateTo}
                setDateTo={setDateTo}
                onValider={() => {
                  apply();
                  setVolet(false);
                }}
              />
            </div>
            <div className="mt-auto flex gap-2">
              {/* Application à la validation, jamais à la frappe, pour la
                  discipline et les dates (#387) : c'est la seule promesse du
                  volet. « Épreuve » garde sa recherche live (#383), comme hors
                  du volet — l'`onKeyDown` Entrée reste un raccourci vers la
                  même validation, pas un second régime. */}
              <Button
                className="flex-1"
                onClick={() => {
                  apply();
                  setVolet(false);
                }}
              >
                Filtrer
              </Button>
              <Button
                variant="ghost"
                onClick={() => {
                  resetVolet();
                  setVolet(false);
                }}
              >
                Réinitialiser ces filtres
              </Button>
            </div>
          </SheetContent>
        </Sheet>
      </CardContent>
    </Card>
  );
}

/**
 * Les quatre filtres repliables, rendus **deux fois** : inline au-dessus de
 * `sm`, dans le volet en dessous. Le suffixe garde les identifiants uniques ;
 * l'état vit chez le parent, les deux rendus affichent donc la même saisie.
 *
 * C'est ce qui évite un `useMediaQuery` : un hook média rendrait la disposition
 * dépendante de l'hydratation, avec le flash que cela implique sur les filtres,
 * première chose vue de l'écran.
 */
function ChampsReplies({
  suffixe,
  eventName,
  setEventName,
  eventType,
  setEventType,
  dateFrom,
  setDateFrom,
  dateTo,
  setDateTo,
  onValider,
}: {
  suffixe: string;
  eventName: string;
  setEventName: (v: string) => void;
  eventType: string;
  setEventType: (v: string) => void;
  dateFrom: string;
  setDateFrom: (v: string) => void;
  dateTo: string;
  setDateTo: (v: string) => void;
  onValider: () => void;
}) {
  return (
    <>
      <Field id={`filtre-epreuve-${suffixe}`} label="Épreuve">
        <Input
          id={`filtre-epreuve-${suffixe}`}
          value={eventName}
          onChange={(e) => setEventName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && onValider()}
          placeholder="Rechercher une épreuve"
          className="w-full sm:w-48"
        />
      </Field>
      <Field id={`filtre-discipline-${suffixe}`} label="Discipline">
        <Select
          value={eventType || ALL}
          onValueChange={(v) => setEventType(v === ALL ? "" : (v as string))}
        >
          <SelectTrigger
            id={`filtre-discipline-${suffixe}`}
            aria-labelledby={`filtre-discipline-${suffixe}-label`}
            className="h-9 w-full sm:w-48"
          >
            <SelectValue placeholder="Toutes les disciplines">
              {(v) => (!v || v === ALL ? "Toutes les disciplines" : eventTypeLabel(v as string))}
            </SelectValue>
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>Toutes les disciplines</SelectItem>
            {EVENT_TYPE_OPTIONS.map((o) => (
              <SelectItem key={o.value} value={o.value}>
                {o.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Field>
      <Field id={`filtre-date-du-${suffixe}`} label="Du">
        <Input
          id={`filtre-date-du-${suffixe}`}
          type="date"
          value={dateFrom}
          onChange={(e) => setDateFrom(e.target.value)}
          className="w-full sm:w-40"
        />
      </Field>
      <Field id={`filtre-date-au-${suffixe}`} label="Au">
        <Input
          id={`filtre-date-au-${suffixe}`}
          type="date"
          value={dateTo}
          onChange={(e) => setDateTo(e.target.value)}
          className="w-full sm:w-40"
        />
      </Field>
    </>
  );
}

/**
 * Libellé **associé** à son champ, et non simplement posé au-dessus.
 *
 * `htmlFor` ne désigne que les contrôles de formulaire étiquetables : le
 * `SelectTrigger` de Base UI étant un `<button>`, il se référence par
 * `aria-labelledby` sur l'`id` du libellé, d'où le `${id}-label`.
 */
function Field({
  id,
  label,
  children,
}: {
  id: string;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex w-full flex-col gap-1.5 sm:w-auto">
      <label
        id={`${id}-label`}
        htmlFor={id}
        className="text-xs font-medium text-[var(--tcn-text-faint)]"
      >
        {label}
      </label>
      {children}
    </div>
  );
}
