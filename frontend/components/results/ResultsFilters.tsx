"use client";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { X } from "lucide-react";
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

  const scope = sp.get("scope") ?? undefined;
  const sort = sp.get("sort") ?? undefined;

  function push(filters: Record<string, string | undefined>) {
    const qs = buildResultsQuery({ ...filters, scope, sort });
    router.push(`/resultats${qs ? `?${qs}` : ""}`);
  }

  function apply() {
    push({
      name,
      event_name: eventName,
      event_type: eventType,
      date_from: dateFrom,
      date_to: dateTo,
    });
  }

  function reset() {
    setName("");
    setEventName("");
    setEventType("");
    setDateFrom("");
    setDateTo("");
    push({});
  }

  // Filtres actifs (depuis l'URL) → chips.
  const active: { key: string; label: string }[] = [];
  if (sp.get("name")) active.push({ key: "name", label: `Athlète : ${sp.get("name")}` });
  if (sp.get("event_name"))
    active.push({ key: "event_name", label: `Course : ${sp.get("event_name")}` });
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
          <Field label="Athlète">
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && apply()}
              placeholder="Rechercher un athlète"
              className="w-48"
            />
          </Field>
          <Field label="Course">
            <Input
              value={eventName}
              onChange={(e) => setEventName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && apply()}
              placeholder="Rechercher une course"
              className="w-48"
            />
          </Field>
          <Field label="Discipline">
            <Select
              value={eventType || ALL}
              onValueChange={(v) => setEventType(v === ALL ? "" : (v as string))}
            >
              <SelectTrigger className="h-9 w-48">
                <SelectValue placeholder="Toutes les disciplines">
                  {(v) =>
                    !v || v === ALL ? "Toutes les disciplines" : eventTypeLabel(v as string)
                  }
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
          <Field label="Du">
            <Input
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="w-40"
            />
          </Field>
          <Field label="Au">
            <Input
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="w-40"
            />
          </Field>
          <div className="flex gap-2">
            <Button onClick={apply}>Filtrer</Button>
            {active.length > 0 && (
              <Button variant="ghost" onClick={reset}>
                Réinitialiser
              </Button>
            )}
          </div>
        </div>

        {active.length > 0 && (
          <div className="flex flex-wrap gap-2 border-t pt-3">
            {active.map((chip) => (
              <Badge key={chip.key} variant="secondary" className="gap-1 pr-1">
                {chip.label}
                <button
                  type="button"
                  onClick={() => removeChip(chip.key)}
                  aria-label={`Retirer ${chip.label}`}
                  className="rounded-sm p-0.5 hover:bg-foreground/10"
                >
                  <X className="size-3" />
                </button>
              </Badge>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-xs font-medium text-muted-foreground">{label}</label>
      {children}
    </div>
  );
}
