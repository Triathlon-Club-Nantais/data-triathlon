import Link from "next/link";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { StatusBadge } from "./StatusBadge";
import { Medal } from "@/components/ui/medal";
import { InitialsAvatar } from "@/components/ui/initials-avatar";
import { Card } from "@/components/ui/card";
import { isTCN } from "@/lib/utils/club";
import { cn } from "@/lib/utils";
import type { Participation } from "@/lib/types";

/** Tableau de classement d'une épreuve (rang général), membres TCN mis en avant. */
export function Leaderboard({
  participations,
}: {
  participations: Participation[];
}) {
  const rows = [...participations].sort((a, b) => {
    const ra = a.rank_overall ?? Number.POSITIVE_INFINITY;
    const rb = b.rank_overall ?? Number.POSITIVE_INFINITY;
    if (ra !== rb) return ra - rb;
    return (a.total_time ?? "").localeCompare(b.total_time ?? "");
  });

  return (
    <Card className="p-0">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-14 text-center">Rang</TableHead>
            <TableHead>Athlète</TableHead>
            <TableHead className="hidden sm:table-cell">Catégorie</TableHead>
            <TableHead className="hidden md:table-cell">Dossard</TableHead>
            <TableHead className="text-right">Temps</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((p) => {
            const name =
              [p.athlete?.prenom, p.athlete?.nom].filter(Boolean).join(" ") ||
              "Athlète";
            const tcn = isTCN(p.club);
            const rank = p.rank_overall;
            return (
              <TableRow
                key={p.id}
                className={cn(
                  tcn && "bg-[color-mix(in_oklch,var(--brand)_10%,transparent)]",
                )}
              >
                <TableCell className="text-center">
                  {rank != null && rank <= 3 ? (
                    <Medal rank={rank} size={24} className="mx-auto" />
                  ) : (
                    <span className="num text-sm font-bold text-muted-foreground">
                      {rank ?? "—"}
                    </span>
                  )}
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-2.5">
                    <InitialsAvatar name={name} size={30} />
                    <div className="min-w-0">
                      <Link
                        href={`/athletes/${p.athlete?.id}`}
                        className="font-medium hover:underline"
                      >
                        {name}
                      </Link>
                      {tcn && (
                        <Badge className="ml-2 align-middle">TCN</Badge>
                      )}
                      {p.club && !tcn && (
                        <span className="ml-2 text-xs text-muted-foreground">
                          {p.club}
                        </span>
                      )}
                    </div>
                  </div>
                </TableCell>
                <TableCell className="hidden text-sm text-muted-foreground sm:table-cell">
                  {p.category ?? "—"}
                </TableCell>
                <TableCell className="num hidden text-sm text-muted-foreground md:table-cell">
                  {p.bib_number ? `#${p.bib_number}` : "—"}
                </TableCell>
                <TableCell className="num text-right font-semibold">
                  {p.total_time ?? (
                    <StatusBadge status={p.status} className="ml-auto" fallback="—" />
                  )}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </Card>
  );
}
