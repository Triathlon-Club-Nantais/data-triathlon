import { Card, CardContent } from "@/components/ui/card";
import { Stat } from "@/components/ui/stat";
import type { Stats } from "@/lib/types";

export function Kpis({ stats }: { stats: Stats }) {
  const items: { label: string; value: number; accent?: boolean }[] = [
    { label: "Résultats importés", value: stats.total, accent: true },
    { label: "Athlètes", value: stats.athletes },
    { label: "Épreuves", value: stats.events },
  ];
  return (
    <div className="grid gap-4 sm:grid-cols-3">
      {items.map((it) => (
        <Card key={it.label}>
          <CardContent className="p-5">
            <Stat value={it.value} label={it.label} accent={it.accent} />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
