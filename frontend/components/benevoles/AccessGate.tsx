"use client";

import { useState } from "react";
import { Button, Card, Input } from "@/components/tcn";
import { apiClient, ApiError } from "@/lib/api/client";

/**
 * Formulaire de mot de passe partagé (#271, US4) — mécanisme d'accès distinct
 * du SSO (research.md §D1 : pas d'identité individuelle, choix RGPD/CNIL).
 */
export function AccessGate({ onSuccess }: { onSuccess: () => void }) {
  const [password, setPassword] = useState("");
  const [erreur, setErreur] = useState<string | null>(null);
  const [enCours, setEnCours] = useState(false);

  async function soumettre(e: React.FormEvent) {
    e.preventDefault();
    setErreur(null);
    setEnCours(true);
    try {
      await apiClient.benevoleLogin(password);
      onSuccess();
    } catch (err) {
      setErreur(
        err instanceof ApiError
          ? err.message
          : "Connexion impossible. Réessayez plus tard.",
      );
    } finally {
      setEnCours(false);
    }
  }

  return (
    <div style={{ maxWidth: 380, margin: "80px auto" }}>
      <Card padding={32}>
        <div style={{ fontFamily: "var(--tcn-font-display)", fontSize: 22, color: "var(--tcn-ink)", marginBottom: 8 }}>
          Vérification des résultats
        </div>
        <div style={{ fontSize: 14, color: "var(--tcn-text-faint)", marginBottom: 20 }}>
          Réservé aux bénévoles chargés de la validation.
        </div>
        <form onSubmit={soumettre}>
          <label htmlFor="benevole-password" style={{ display: "block", fontSize: 13, fontWeight: 600, marginBottom: 6, color: "var(--tcn-text-body)" }}>
            Mot de passe
          </label>
          <Input
            id="benevole-password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            status={erreur ? "error" : "default"}
            autoFocus
            style={{ width: "100%" }}
          />
          {erreur && (
            <div style={{ color: "var(--tcn-danger-text)", fontSize: 13, marginTop: 8 }}>{erreur}</div>
          )}
          <Button type="submit" disabled={enCours || !password} style={{ width: "100%", marginTop: 16 }}>
            {enCours ? "Connexion…" : "Se connecter"}
          </Button>
        </form>
      </Card>
    </div>
  );
}
