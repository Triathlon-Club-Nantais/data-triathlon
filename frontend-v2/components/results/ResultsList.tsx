"use client";
import { toast } from "sonner";
import { EventGroup } from "./EventGroup";
import { useDeleteParticipation } from "@/lib/queries/participations";
import { useRouter } from "next/navigation";
import type { Participation } from "@/lib/types";

export function ResultsList({ initial }: { initial: Participation[] }) {
  const del = useDeleteParticipation();
  const router = useRouter();

  async function onDelete(id: number) {
    try {
      await del.mutateAsync(id);
      toast.success("Résultat supprimé.");
      router.refresh();
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  return <EventGroup participations={initial} onDelete={onDelete} />;
}
