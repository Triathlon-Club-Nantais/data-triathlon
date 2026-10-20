import { apiServer } from "@/lib/api/server";

/**
 * Ce que l'écran du code d'accès dit de la connexion des adhérents (#1322) :
 * la proposer à un anonyme quand un moyen existe, expliquer à un connecté
 * non adhérent pourquoi sa session ne suffit pas. `null` : rien à dire.
 */
export type ConnexionAdherent = "proposee" | "non-adherent" | null;

/**
 * Lu seulement quand l'accès est refusé : une panne retombe sur `null`, le
 * formulaire du code restant le moyen d'entrer.
 */
export async function connexionAdherent(): Promise<ConnexionAdherent> {
  const [methodes, session] = await Promise.all([
    apiServer.listAuthMethods().catch(() => []),
    apiServer.getSession().catch(() => null),
  ]);
  if (session) return session.is_member ? null : "non-adherent";
  // Une méthode d'administration seule ne connecte aucun adhérent (#1666).
  return methodes.some((methode) => methode.audience !== "admin") ? "proposee" : null;
}
