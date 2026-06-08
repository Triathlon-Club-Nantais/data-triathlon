"use client";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { eventTypeLabel } from "@/lib/constants";
import { formatMonth } from "@/lib/utils/date";
import type { Stats } from "@/lib/types";

export function ClubStats({ stats }: { stats: Stats }) {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-3">
        <Kpi label="Résultats" value={stats.total} />
        <Kpi label="Athlètes" value={stats.athletes} />
        <Kpi label="Épreuves" value={stats.events} />
      </div>

      <Tabs defaultValue="type">
        <TabsList>
          <TabsTrigger value="type">Par type</TabsTrigger>
          <TabsTrigger value="month">Par mois</TabsTrigger>
        </TabsList>
        <TabsContent value="type">
          <DistributionList
            entries={Object.entries(stats.by_type)}
            labeller={(k) => eventTypeLabel(k)}
          />
        </TabsContent>
        <TabsContent value="month">
          <DistributionList
            entries={Object.entries(stats.by_month)}
            labeller={(k) => formatMonth(k)}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function Kpi({ label, value }: { label: string; value: number }) {
  return (
    <Card>
      <CardContent className="p-5">
        <div className="text-3xl font-extrabold">{value}</div>
        <div className="text-sm text-muted-foreground">{label}</div>
      </CardContent>
    </Card>
  );
}

function DistributionList({
  entries,
  labeller,
}: {
  entries: [string, number][];
  labeller: (key: string) => string;
}) {
  const max = Math.max(1, ...entries.map(([, v]) => v));
  return (
    <div className="space-y-2 pt-3">
      {entries.map(([key, value]) => (
        <div key={key} className="flex items-center gap-3">
          <span className="w-40 shrink-0 text-sm">{labeller(key)}</span>
          <div className="h-3 flex-1 overflow-hidden rounded bg-muted">
            <div className="h-full bg-primary" style={{ width: `${(value / max) * 100}%` }} />
          </div>
          <span className="w-10 text-right text-sm font-medium">{value}</span>
        </div>
      ))}
    </div>
  );
}
