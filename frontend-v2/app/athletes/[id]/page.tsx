import { notFound } from "next/navigation";
import { apiServer } from "@/lib/api/server";
import { ResultCard } from "@/components/results/ResultCard";

export default async function AthletePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const data = await apiServer.getAthlete(Number(id)).catch(() => null);
  if (!data) notFound();
  const { athlete, participations } = data;
  const fullName = [athlete.prenom, athlete.nom].filter(Boolean).join(" ");

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">{fullName}</h1>
        <p className="text-muted-foreground">
          {athlete.club ?? "Sans club"} · {participations.length} résultat
          {participations.length > 1 ? "s" : ""}
        </p>
      </div>
      <div className="space-y-3">
        {participations.map((p) => (
          <ResultCard key={p.id} result={p} />
        ))}
      </div>
    </div>
  );
}
