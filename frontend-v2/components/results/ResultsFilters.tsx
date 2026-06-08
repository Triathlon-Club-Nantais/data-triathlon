"use client";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { EVENT_TYPE_OPTIONS } from "@/lib/constants";

export function buildResultsQuery(filters: Record<string, string | undefined>): string {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([k, v]) => {
    if (v && v !== "") params.set(k, v);
  });
  return params.toString();
}

export function ResultsFilters() {
  const router = useRouter();
  const sp = useSearchParams();
  const [name, setName] = useState(sp.get("name") ?? "");
  const [eventType, setEventType] = useState(sp.get("event_type") ?? "");
  const [dateFrom, setDateFrom] = useState(sp.get("date_from") ?? "");
  const [dateTo, setDateTo] = useState(sp.get("date_to") ?? "");

  function apply() {
    const qs = buildResultsQuery({
      name,
      event_type: eventType,
      date_from: dateFrom,
      date_to: dateTo,
    });
    router.push(`/resultats${qs ? `?${qs}` : ""}`);
  }

  function reset() {
    setName("");
    setEventType("");
    setDateFrom("");
    setDateTo("");
    router.push("/resultats");
  }

  return (
    <div className="flex flex-wrap items-end gap-3 rounded-md border p-4">
      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium">Nom</label>
        <Input value={name} onChange={(e) => setName(e.target.value)} className="w-48" />
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium">Type</label>
        <select
          className="h-9 rounded-md border bg-background px-2"
          value={eventType}
          onChange={(e) => setEventType(e.target.value)}
        >
          <option value="">Tous</option>
          {EVENT_TYPE_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium">Du</label>
        <Input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium">Au</label>
        <Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
      </div>
      <Button onClick={apply}>Filtrer</Button>
      <Button variant="ghost" onClick={reset}>Réinitialiser</Button>
    </div>
  );
}
