import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { RETOUR_CONNEXION_KEY } from "@/lib/constants";
import { NAV_WIDTH_COOKIE } from "@/lib/nav-cookies";
import { LegalPage } from "../LegalPage";
import { PRIVACY_POLICY } from "./confidentialite";

function rendre() {
  render(<LegalPage document={PRIVACY_POLICY} />);
  return document.body.textContent ?? "";
}

function rubrique(title: RegExp) {
  return screen.getByRole("heading", { level: 2, name: title });
}

describe("Politique de confidentialité (#333)", () => {
  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN", "test-token");
    vi.stubEnv("NEXT_PUBLIC_POSTHOG_HOST", "https://eu.posthog.com");
  });

  it("porte les rubriques exigées par l'issue", () => {
    rendre();
    rubrique(/responsable/i);
    rubrique(/données/i);
    rubrique(/pourquoi/i);
    rubrique(/combien de temps/i);
    rubrique(/qui y a accès/i);
    rubrique(/vos droits/i);
    rubrique(/cnil/i);
    rubrique(/cookies/i);
  });

  it("nomme les données collectées et leur provenance", () => {
    const texte = rendre();
    for (const donnee of ["nom", "prénom", "sexe", "catégorie d'âge", "club", "temps", "classement"]) {
      expect(texte).toContain(donnee);
    }
    for (const chronometreur of [
      "Klikego",
      "Breizh Chrono",
      "TimePulse",
      "Sportinnovation",
      "ProLiveSport",
      "Chronoplace",
      "Wiclax",
      "RaceResult",
      "T2Area",
      "Competitor",
      "ok-time",
      "runnerbreizh",
      "Sporthive",
      "chronoweb",
    ]) {
      expect(texte).toContain(chronometreur);
    }
    expect(texte).toMatch(/liste de liens/i);
    expect(texte).not.toMatch(/import de fichiers/i);
    expect(texte).toMatch(/saisie manuelle/i);
    expect(texte).toMatch(/école de triathlon/i);
  });

  it("annonce la base légale retenue par la décision #332", () => {
    expect(rendre()).toMatch(/intérêt légitime/i);
  });

  it("donne les durées de conservation de la décision #332", () => {
    const texte = rendre();
    expect(texte).toMatch(/tant que le service existe/i);
    expect(texte).toMatch(/12 mois/);
    expect(texte).toMatch(/90 jours/);
  });

  it("liste les sous-traitants et signale les transferts hors Union européenne", () => {
    const texte = rendre();
    for (const prestataire of ["Vercel", "Render", "Microsoft", "Supabase", "GitHub", "PostHog"]) {
      expect(texte).toContain(prestataire);
    }
    expect(texte).toMatch(/hors de l'Union européenne/i);
  });

  it("dit comment exercer ses droits, opposition comprise", () => {
    const texte = rendre();
    expect(texte).toMatch(/opposition/i);
    expect(texte).toMatch(/un mois/i);
    for (const lien of screen.getAllByRole("link", { name: "president@triathlon-club-nantais.com" })) {
      expect(lien).toHaveAttribute("href", "mailto:president@triathlon-club-nantais.com");
    }
  });

  it("mentionne le droit de réclamation auprès de la CNIL", () => {
    rendre();
    expect(screen.getByRole("link", { name: /cnil\.fr\/fr\/plaintes/ })).toHaveAttribute(
      "href",
      "https://www.cnil.fr/fr/plaintes",
    );
  });

  it("liste les cookies et le stockage du navigateur", () => {
    const texte = rendre();
    for (const traceur of [
      "tcn_session",
      "tcn_auth_state",
      "tcn_logged_in",
      "tcn_site_session",
      "tcn_benevole_session",
      "tcn-athlete",
      NAV_WIDTH_COOKIE,
      RETOUR_CONNEXION_KEY,
    ]) {
      expect(texte).toContain(traceur);
    }
  });

  it("dit ce que la mesure d'audience reçoit, sans accord et avec (#1159)", () => {
    const texte = rendre();
    expect(texte).toMatch(/sans cookie/);
    expect(texte).toMatch(/adresse électronique, son nom affiché et ses rôles lui sont transmis/);
    expect(texte).toContain("tcn-analytics-consent");
    expect(screen.getByRole("button", { name: "Refuser la mesure détaillée" })).toBeInTheDocument();
    expect(screen.getByRole("row", { name: /^ph_/ })).toHaveTextContent("1 an");
  });
});
