"use client";
import { Loader2 } from "lucide-react";
import { ResultCard } from "./ResultCard";
import { useCourseParticipations } from "@/lib/queries/events";

/**
 * Participants d'une épreuve, montés uniquement au dépliage de l'accordéon
 * (le panneau base-ui démonte son contenu quand il est fermé) → chargement à la
 * demande, et seulement les participants visibles dans le scope courant.
 */
export function EventParticipations({
  courseId,
  club,
  name,
  onDelete,
}: {
  courseId: number;
  club?: string;
  name?: string;
  onDelete?: (id: number) => void;
}) {
  const { data, isLoading, isError } = useCourseParticipations(courseId, { club, name });

  if (isLoading) {
    return (
      <div className="flex justify-center py-6 text-muted-foreground">
        <Loader2 className="size-5 animate-spin" />
      </div>
    );
  }
  if (isError) {
    return (
      <p className="py-4 text-center text-sm text-destructive">
        Impossible de charger les participants.
      </p>
    );
  }

  const items = data ?? [];
  if (items.length === 0) {
    return <p className="py-4 text-center text-sm text-muted-foreground">Aucun participant.</p>;
  }
  return (
    <>
      {items.map((p) => (
        <ResultCard key={p.id} result={p} onDelete={onDelete} />
      ))}
    </>
  );
}
