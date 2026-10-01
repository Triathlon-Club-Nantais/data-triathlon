"use client";
import { useState, type FormEvent } from "react";
import { Button } from "./Button";
import { Input } from "./Input";
import { Modal } from "./Modal";
import { apiClient, ApiError } from "@/lib/api/client";

/**
 * Bouton flottant de signalement (#267) — accessible à tout visiteur, connecté
 * ou non. Le champ honeypot est invisible et hors du parcours clavier
 * (research.md §D2) : un humain ne le rencontre jamais, un bot générique qui
 * remplit tous les champs du DOM s'y trahit.
 */
export function FeedbackButton() {
  const [open, setOpen] = useState(false);
  const [type, setType] = useState<"bug" | "feedback" | "retrait">("bug");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [honeypot, setHoneypot] = useState("");
  const [erreur, setErreur] = useState<string | null>(null);
  const [invalides, setInvalides] = useState({ titre: false, description: false });
  const [envoi, setEnvoi] = useState(false);
  const [envoye, setEnvoye] = useState(false);

  // Le brouillon survit à la fermeture : seul un envoi réussi le vide (#1114).
  function fermer() {
    setOpen(false);
    setErreur(null);
    setInvalides({ titre: false, description: false });
    if (envoye) {
      setType("bug");
      setTitle("");
      setBody("");
      setHoneypot("");
      setEnvoye(false);
    }
  }

  const saisieEnCours = !envoye && Boolean(title.trim() || body.trim());

  async function soumettre(e: FormEvent) {
    e.preventDefault();
    const manquants = { titre: !title.trim(), description: !body.trim() };
    if (manquants.titre || manquants.description) {
      setErreur(
        manquants.titre && manquants.description
          ? "Le titre et la description sont obligatoires."
          : manquants.titre
            ? "Le titre est obligatoire."
            : "La description est obligatoire.",
      );
      setInvalides(manquants);
      return;
    }
    setErreur(null);
    setInvalides({ titre: false, description: false });
    setEnvoi(true);
    try {
      await apiClient.submitFeedback({
        type,
        title: title.trim(),
        body: body.trim(),
        page_url: typeof window !== "undefined" ? window.location.href : null,
        user_agent: typeof navigator !== "undefined" ? navigator.userAgent : null,
        honeypot: honeypot || null,
      });
      setEnvoye(true);
    } catch (err) {
      setErreur(err instanceof ApiError ? err.message : "Erreur réseau, réessayez.");
    } finally {
      setEnvoi(false);
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Signaler un bug ou laisser un retour"
        // Sous `md`, la barre basse mobile (#482, NAV-4) occupe déjà le bas de
        // l'écran : décalé au-dessus d'elle, sans quoi elle en couvrirait une
        // bonne partie et intercepterait les appuis sur sa destination la
        // plus à droite.
        className="bottom-[calc(24px+var(--tcn-nav-bottom))] md:bottom-6"
        style={{
          position: "fixed",
          right: 24,
          zIndex: 40,
          width: 52,
          height: 52,
          borderRadius: "50%",
          background: "var(--tcn-orange)",
          color: "#fff",
          border: "none",
          boxShadow: "var(--tcn-shadow-modal)",
          fontSize: 22,
          cursor: "pointer",
        }}
      >
        💬
      </button>

      {open ? (
        <Modal
          open={open}
          eyebrow="Retour"
          title="Signaler un bug ou laisser un avis"
          onClose={fermer}
          width={440}
          dismissible={!saisieEnCours}
        >
          {envoye ? (
            <div>
              <p style={{ color: "var(--tcn-text)" }}>
                Merci, votre signalement a bien été envoyé.
              </p>
              <Button onClick={fermer} style={{ marginTop: 16 }}>
                Fermer
              </Button>
            </div>
          ) : (
            <form onSubmit={soumettre} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              <div role="radiogroup" aria-label="Type de retour" style={{ display: "flex", gap: 16 }}>
                <label style={{ display: "flex", alignItems: "center", gap: 6, color: "var(--tcn-text)" }}>
                  <input
                    type="radio"
                    name="feedback-type"
                    value="bug"
                    checked={type === "bug"}
                    onChange={() => setType("bug")}
                  />
                  Bug
                </label>
                <label style={{ display: "flex", alignItems: "center", gap: 6, color: "var(--tcn-text)" }}>
                  <input
                    type="radio"
                    name="feedback-type"
                    value="feedback"
                    checked={type === "feedback"}
                    onChange={() => setType("feedback")}
                  />
                  Avis / suggestion
                </label>
                <label style={{ display: "flex", alignItems: "center", gap: 6, color: "var(--tcn-text)" }}>
                  <input
                    type="radio"
                    name="feedback-type"
                    value="retrait"
                    checked={type === "retrait"}
                    onChange={() => setType("retrait")}
                  />
                  Retrait de mes données
                </label>
              </div>
              {type === "retrait" && (
                // Le droit d'opposition (#334) : ce qu'il faut pour retrouver les résultats, et le délai dû.
                <p style={{ color: "var(--tcn-text-muted)", fontSize: 14 }}>
                  Indiquez votre nom, prénom et l&apos;épreuve concernée (nom et date). Vos résultats seront
                  rendus anonymes ; le club vous répond sous un mois.
                </p>
              )}

              <Input
                placeholder="Titre court"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                maxLength={200}
                aria-label="Titre"
                aria-invalid={invalides.titre || undefined}
                aria-describedby={invalides.titre ? "feedback-erreur" : undefined}
              />

              <textarea
                placeholder="Décrivez le problème ou votre retour"
                value={body}
                onChange={(e) => setBody(e.target.value)}
                rows={5}
                maxLength={10000}
                aria-label="Description"
                aria-invalid={invalides.description || undefined}
                aria-describedby={invalides.description ? "feedback-erreur" : undefined}
                style={{
                  padding: "13px 16px",
                  background: "var(--tcn-fill)",
                  border: "1.5px solid var(--tcn-border)",
                  borderRadius: "var(--tcn-radius-xl)",
                  color: "var(--tcn-text)",
                  fontFamily: "var(--tcn-font-body)",
                  fontSize: 15,
                  resize: "vertical",
                }}
              />

              {/* Honeypot — invisible et hors du parcours clavier (research.md §D2) */}
              <input
                type="text"
                name="site_web"
                value={honeypot}
                onChange={(e) => setHoneypot(e.target.value)}
                tabIndex={-1}
                aria-hidden="true"
                autoComplete="off"
                style={{ position: "absolute", left: "-9999px", width: 1, height: 1, opacity: 0 }}
              />

              {erreur ? (
                <p id="feedback-erreur" role="alert" style={{ color: "var(--tcn-danger-text)", fontSize: 14 }}>
                  {erreur}
                </p>
              ) : null}

              <Button type="submit" disabled={envoi}>
                {envoi ? "Envoi…" : "Envoyer"}
              </Button>
            </form>
          )}
        </Modal>
      ) : null}
    </>
  );
}
