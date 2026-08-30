"use client";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { useAdminUsers } from "@/lib/queries/admin";
import { useAdminCreateVolunteerDeclaration } from "@/lib/queries/admin";

/**
 * Formulaire admin « Déclarer pour un membre » (#751, US2) — réservé à
 * `benevolat:manage`, validée d'office (FR-004). Patron `GroupDetailDialog` :
 * `<select>` natif pour choisir le membre.
 */
export function AdminVolunteerDeclarationCreateForm() {
  const utilisateurs = useAdminUsers();
  const creer = useAdminCreateVolunteerDeclaration();
  const [beneficiaryId, setBeneficiaryId] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [erreur, setErreur] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!beneficiaryId || !title.trim() || !description.trim()) {
      setErreur("Le membre, le titre et la description sont obligatoires.");
      return;
    }
    setErreur(null);
    try {
      await creer.mutateAsync({
        beneficiary_user_id: Number(beneficiaryId),
        title: title.trim(),
        description: description.trim(),
      });
      setBeneficiaryId("");
      setTitle("");
      setDescription("");
      toast.success("Déclaration créée, validée d'office.");
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  return (
    <Card className="p-6">
      <form onSubmit={onSubmit} className="space-y-3">
        <div className="space-y-1.5">
          <Label htmlFor="benevolat-admin-membre">Membre</Label>
          <select
            id="benevolat-admin-membre"
            className="border-input h-9 w-full rounded-md border bg-transparent px-2 text-sm"
            value={beneficiaryId}
            onChange={(e) => setBeneficiaryId(e.target.value)}
          >
            <option value="" disabled>
              Choisir un membre…
            </option>
            {(utilisateurs.data ?? []).map((u) => (
              <option key={u.id} value={u.id}>
                {u.display_name || u.email}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="benevolat-admin-titre">Titre</Label>
          <Input
            id="benevolat-admin-titre"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            maxLength={200}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="benevolat-admin-description">Description</Label>
          <textarea
            id="benevolat-admin-description"
            className="border-input min-h-20 w-full rounded-md border bg-transparent px-2 py-1.5 text-sm"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            maxLength={10000}
          />
        </div>
        {erreur && (
          <p role="alert" className="text-destructive text-sm">
            {erreur}
          </p>
        )}
        <Button type="submit" disabled={creer.isPending}>
          Déclarer pour ce membre
        </Button>
      </form>
    </Card>
  );
}
