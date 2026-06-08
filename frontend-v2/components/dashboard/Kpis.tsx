import { Card, CardContent } from "@/components/ui/card";
import type { Stats } from "@/lib/types";

export function Kpis({ stats }: { stats: Stats }) {
  const items = [
    { label: "Résultats importés", value: stats.total },
    { label: "Athlètes", value: stats.athletes },
    { label: "Épreuves", value: stats.events },
  ];
  return (
    <div className="grid gap-4 sm:grid-cols-3">
      {items.map((it) => (
        <Card key={it.label}>
          <CardContent className="p-5">
            <div className="text-3xl font-extrabold">{it.value}</div>
            <div className="text-sm text-muted-foreground">{it.label}</div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
