"use client";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { useProviderQuality } from "@/lib/queries/admin";
import { messageDeRefus } from "@/lib/api/refus";
import { providerLabel } from "@/lib/labels";
import { QUALITY_ISSUE_LABELS } from "@/lib/quality";

const DENIAL = { sujet: "chiffres de fiabilité", action: "consulter la fiabilité par fournisseur" };

const NUMERIC_CELL = "text-right tabular-nums";
// Le nom reste à l'écran quand les colonnes d'anomalie défilent à l'horizontale.
const STICKY_CELL = "sticky left-0 bg-card";

/**
 * Fournisseur × anomalie (#1366) : ce que coûterait le retrait d'un fournisseur
 * (#1342). Une colonne par anomalie présente, la plus fréquente d'abord ; une
 * cellule compte les épreuves non fiables qui portent ce code.
 */
export function ProviderQualityTable() {
  const { data, isPending, error } = useProviderQuality();

  if (isPending)
    return (
      <div role="status">
        <Skeleton className="h-40 w-full" />
        <span className="sr-only">Chargement du tableau</span>
      </div>
    );
  if (error) return <EmptyState {...messageDeRefus(error, DENIAL)} />;
  if (data.length === 0)
    return (
      <EmptyState
        title="Aucune épreuve importée depuis un fournisseur"
        description="Le tableau se remplit à mesure des imports depuis un fournisseur de chronométrage."
      />
    );

  const totals = new Map<string, number>();
  for (const row of data)
    for (const [code, n] of Object.entries(row.anomalies))
      totals.set(code, (totals.get(code) ?? 0) + n);
  const codes = [...totals].sort((a, b) => b[1] - a[1]).map(([code]) => code);

  return (
    <Card className="p-0">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className={STICKY_CELL}>Fournisseur</TableHead>
            <TableHead className={NUMERIC_CELL}>Épreuves</TableHead>
            <TableHead className={NUMERIC_CELL}>Non fiables</TableHead>
            {codes.map((code) => (
              <TableHead key={code} className={`${NUMERIC_CELL} whitespace-normal`}>
                {QUALITY_ISSUE_LABELS[code] ?? code}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.map((row) => (
            <TableRow key={row.provider}>
              <TableHead scope="row" className={`${STICKY_CELL} font-medium`}>
                {providerLabel(row.provider)}
              </TableHead>
              <TableCell className={NUMERIC_CELL}>{row.course_count}</TableCell>
              <TableCell className={NUMERIC_CELL}>{row.unreliable_count}</TableCell>
              {codes.map((code) => (
                <TableCell key={code} className={NUMERIC_CELL}>
                  {row.anomalies[code] ?? 0}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Card>
  );
}
