"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button, Card, Input } from "@/components/tcn";
import { apiClient, ApiError } from "@/lib/api/client";

/**
 * Formulaire du mot de passe partagé au site (#509) — patron `AccessGate` (#271).
 *
 * `apres` dit où aller après une connexion réussie, et les deux valeurs
 * correspondent aux deux façons dont ce formulaire s'affiche :
 *
 * - `"rafraichir"` (défaut) — rendu **sur place** par `app/(protege)/layout.tsx`
 *   à la place de la page demandée. L'URL est déjà la bonne : rejouer le layout
 *   suffit, et c'est ce qui préserve la destination d'un lien partagé vers
 *   `/courses/42` (relevé en revue de #513 — tout finissait sur le tableau de
 *   bord). Un `push` ferait perdre la page qu'on voulait voir.
 * - `"accueil"` — page `/acces`, atteinte en direct ou après déconnexion. Aucune
 *   page n'était demandée, et un rafraîchissement ne ferait que réafficher ce
 *   formulaire.
 */
export function SiteAccessGate({ apres = "rafraichir" }: { apres?: "rafraichir" | "accueil" }) {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [erreur, setErreur] = useState<string | null>(null);
  const [enCours, setEnCours] = useState(false);

  async function soumettre(e: React.FormEvent) {
    e.preventDefault();
    setErreur(null);
    setEnCours(true);
    try {
      await apiClient.siteAccessLogin(password);
      if (apres === "accueil") {
        router.push("/");
      } else {
        router.refresh();
      }
    } catch (err) {
      setErreur(
        err instanceof ApiError ? err.message : "Connexion impossible. Réessayez plus tard.",
      );
    } finally {
      setEnCours(false);
    }
  }

  return (
    <div style={{ maxWidth: 380, margin: "80px auto" }}>
      <Card padding={32}>
        <h1
          style={{
            fontFamily: "var(--tcn-font-display)",
            fontSize: 22,
            color: "var(--tcn-ink)",
            fontWeight: 400,
            margin: 0,
            marginBottom: 8,
          }}
        >
          Accès réservé aux adhérents
        </h1>
        <div style={{ fontSize: 14, color: "var(--tcn-text-faint)", marginBottom: 20 }}>
          Le mot de passe vous a été communiqué par le club.
        </div>
        <form onSubmit={soumettre}>
          <label
            htmlFor="site-password"
            style={{ display: "block", fontSize: 13, fontWeight: 600, marginBottom: 6, color: "var(--tcn-text-body)" }}
          >
            Mot de passe
          </label>
          <Input
            id="site-password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            status={erreur ? "error" : "default"}
            aria-describedby={erreur ? "site-password-erreur" : undefined}
            autoFocus
            style={{ width: "100%" }}
          />
          {erreur && (
            <div id="site-password-erreur" role="alert" style={{ color: "var(--tcn-danger-text)", fontSize: 13, marginTop: 8 }}>
              {erreur}
            </div>
          )}
          <Button type="submit" disabled={enCours || !password} style={{ width: "100%", marginTop: 16 }}>
            {enCours ? "Connexion…" : "Se connecter"}
          </Button>
        </form>
      </Card>
    </div>
  );
}
