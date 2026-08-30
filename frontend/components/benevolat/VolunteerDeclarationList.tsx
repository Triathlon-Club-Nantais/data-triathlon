"use client";
import { toast } from "sonner";
import { Badge, Button, Card } from "@/components/tcn";
import { useDangerConfirm } from "@/components/admin/DangerConfirm";
import {
  useDeleteMyVolunteerDeclaration,
  useMyVolunteerDeclarations,
} from "@/lib/queries/volunteer-declarations";
import type { VolunteerDeclaration } from "@/lib/types";
import { formatDate } from "@/lib/utils/date";

const LIBELLE_STATUT: Record<string, string> = {
  en_attente: "En attente de validation",
  validee: "Validée",
};

/** Liste des déclarations de bénévolat du membre connecté (#751, FR-009,
 * FR-006 pour la suppression — US4). */
export function VolunteerDeclarationList() {
  const { data, isLoading, error } = useMyVolunteerDeclarations();
  const supprimer = useDeleteMyVolunteerDeclaration();
  const confirmerLeDanger = useDangerConfirm();

  if (isLoading) return null;
  if (error) {
    return (
      <p style={{ color: "var(--tcn-text-muted)" }}>
        Impossible de charger vos déclarations pour le moment.
      </p>
    );
  }
  if (!data || data.length === 0) {
    return (
      <Card variant="dashed">
        <p style={{ margin: 0, color: "var(--tcn-text-muted)" }}>
          Aucune déclaration de bénévolat pour l&apos;instant — utilisez le formulaire
          ci-dessus pour en ajouter une.
        </p>
      </Card>
    );
  }

  async function onDelete(declaration: VolunteerDeclaration) {
    const confirme = await confirmerLeDanger({
      titre: `Supprimer « ${declaration.title} » ?`,
      description: "Cette déclaration sera définitivement supprimée, sans trace.",
      libelleAction: "Supprimer",
    });
    if (!confirme) return;
    try {
      await supprimer.mutateAsync(declaration.id);
      toast.success("Déclaration supprimée.");
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  return (
    <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 12 }}>
      {data.map((declaration) => (
        <li key={declaration.id}>
          <Card padding={18}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
              <div>
                <p style={{ margin: 0, fontWeight: 700 }}>{declaration.title}</p>
                <p style={{ margin: "4px 0 0", color: "var(--tcn-text-muted)", fontSize: 14 }}>
                  {declaration.description}
                </p>
                <p style={{ margin: "6px 0 0", color: "var(--tcn-text-faint)", fontSize: 13 }}>
                  {formatDate(declaration.created_at)}
                </p>
              </div>
              <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 8 }}>
                <Badge variant={declaration.status === "validee" ? "orange" : "neutral"}>
                  {LIBELLE_STATUT[declaration.status] ?? declaration.status}
                </Badge>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onDelete(declaration)}
                  disabled={supprimer.isPending}
                >
                  Supprimer
                </Button>
              </div>
            </div>
          </Card>
        </li>
      ))}
    </ul>
  );
}
