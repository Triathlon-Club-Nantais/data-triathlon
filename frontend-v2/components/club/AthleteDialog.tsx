"use client";
import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { apiClient } from "@/lib/api/client";
import { ResultCard } from "@/components/results/ResultCard";
import { Skeleton } from "@/components/ui/skeleton";
import type { AthleteDetail } from "@/lib/types";

export function AthleteDialog({
  athleteId,
  open,
  onOpenChange,
}: {
  athleteId: number | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [data, setData] = useState<AthleteDetail | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open || athleteId == null) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    setData(null);
    apiClient
      .getAthlete(athleteId)
      .then(setData)
      .finally(() => setLoading(false));
  }, [athleteId, open]);

  const name = data ? [data.athlete.prenom, data.athlete.nom].filter(Boolean).join(" ") : "";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[80vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{name || "Athlète"}</DialogTitle>
        </DialogHeader>
        {loading && <Skeleton className="h-32 w-full" />}
        {data && (
          <div className="space-y-3">
            {data.participations.map((p) => (
              <ResultCard key={p.id} result={p} />
            ))}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
