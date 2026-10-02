import type { Feedback } from "@/lib/types";

/** Libellé et teinte du type d'un retour utilisateur, partagés par la file et le détail. */
export const FEEDBACK_TYPE_BADGE: Record<
  Feedback["type"],
  { label: string; variant: "destructive" | "secondary" | "outline" }
> = {
  bug: { label: "Bug", variant: "destructive" },
  feedback: { label: "Retour", variant: "secondary" },
  // Demande d'opposition (#334) : elle se traite depuis l'écran des oppositions.
  retrait: { label: "Retrait de données", variant: "outline" },
};
