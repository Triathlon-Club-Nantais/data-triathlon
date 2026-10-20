import { FileUser, Medal, Users } from "lucide-react";

/**
 * La sorte d'une demande de la file commune (#1637) : rattacher une fiche
 * entière (#1325), déplacer un seul résultat, ou ajouter l'auteur à la
 * composition d'un relais (#1739). Pastille et icône distinctes
 * (un contour pour les sortes autres que la fiche entière), pour ne jamais
 * confondre les gestes.
 */
const SORTES = {
  record: { Icone: FileUser, libelle: "Fiche entière" },
  result: { Icone: Medal, libelle: "Un résultat" },
  team: { Icone: Users, libelle: "Résultat d'équipe" },
} as const;

export function ClaimKind({ kind }: { kind: keyof typeof SORTES }) {
  const { Icone, libelle } = SORTES[kind];
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold"
      style={
        kind === "record"
          ? { background: "var(--tcn-orange-08)", color: "var(--tcn-orange-deeper)" }
          : // Contour plutôt qu'aplat : `--tcn-fill` vaut le fond de page et ne se verrait pas.
            { border: "1.5px solid var(--tcn-border)", color: "var(--tcn-ink)" }
      }
    >
      <Icone aria-hidden size={14} />
      {libelle}
    </span>
  );
}
