"use client";
import { useId, useState } from "react";
import { toast } from "sonner";
import { Button, Card, Input } from "@/components/tcn";
import { useCreateVolunteerDeclaration } from "@/lib/queries/volunteer-declarations";

/**
 * Formulaire self-service de déclaration de bénévolat (#751). Toujours une
 * auto-déclaration — aucun champ bénéficiaire, cf. `VolunteerDeclarationCreate`
 * (le schéma backend n'en expose aucun non plus, FR-003).
 */
export function VolunteerDeclarationForm() {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [erreur, setErreur] = useState<string | null>(null);
  const descriptionId = useId();
  const create = useCreateVolunteerDeclaration();

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim() || !description.trim()) {
      setErreur("Le titre et la description sont obligatoires.");
      return;
    }
    setErreur(null);
    try {
      await create.mutateAsync({ title: title.trim(), description: description.trim() });
      setTitle("");
      setDescription("");
      toast.success("Déclaration enregistrée, en attente de validation.");
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  return (
    <Card>
      <form onSubmit={onSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <div>
          <label htmlFor="benevolat-titre" style={{ display: "block", fontWeight: 700, marginBottom: 6 }}>
            Titre
          </label>
          <Input
            id="benevolat-titre"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Ex. Ravitaillement 10km du Lac"
            maxLength={200}
          />
        </div>
        <div>
          <label htmlFor={descriptionId} style={{ display: "block", fontWeight: 700, marginBottom: 6 }}>
            Description
          </label>
          <textarea
            id={descriptionId}
            className="tcn-input"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Décrivez l'activité de bénévolat effectuée"
            maxLength={10000}
            rows={4}
            style={{ width: "100%", resize: "vertical" }}
          />
        </div>
        {erreur && (
          <p role="alert" style={{ color: "var(--tcn-danger-text)", fontSize: 14, margin: 0 }}>
            {erreur}
          </p>
        )}
        <Button type="submit" disabled={create.isPending} style={{ alignSelf: "flex-start" }}>
          Déclarer cette activité
        </Button>
      </form>
    </Card>
  );
}
