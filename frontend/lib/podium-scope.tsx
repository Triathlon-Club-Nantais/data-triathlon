import { Trophy, Ribbon, Users, type LucideIcon } from "lucide-react";

export type PodiumScope = "overall" | "category" | "gender";

/**
 * Icône + libellés par scope de podium (#128) — partagés entre `PodiumsList`
 * (badge sur la médaille) et `ClubDashboard` (roster « Athlètes du club »).
 * Le `title` sert de tooltip natif au survol : il explicite ce que dit l'icône
 * seule ne peut pas dire (« top 3 dans sa catégorie d'âge ») sans redoubler le
 * badge textuel déjà présent à côté.
 */
export const PODIUM_SCOPE_META: Record<
  PodiumScope,
  { Icon: LucideIcon; label: string; title: string }
> = {
  overall: {
    Icon: Trophy,
    label: "Podium général",
    title: "Podium général (top 3 scratch)",
  },
  category: {
    Icon: Ribbon,
    label: "Podium de catégorie",
    title: "Podium de catégorie (top 3 dans sa catégorie d'âge)",
  },
  gender: {
    Icon: Users,
    label: "Podium de genre",
    title: "Podium de genre (top 3 dans son sexe)",
  },
};
