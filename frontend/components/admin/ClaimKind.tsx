import { FileUser, Medal } from "lucide-react";

/**
 * La sorte d'une demande de la file commune (#1637) : rattacher une fiche
 * entière (#1325) ou déplacer un seul résultat. Pastille, icône et teinte
 * distinctes, pour ne jamais confondre les deux gestes.
 */
export function ClaimKind({ kind }: { kind: "record" | "result" }) {
  const fiche = kind === "record";
  const Icone = fiche ? FileUser : Medal;
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold"
      style={
        fiche
          ? { background: "var(--tcn-orange-08)", color: "var(--tcn-orange-deeper)" }
          : // Contour plutôt qu'aplat : `--tcn-fill` vaut le fond de page et ne se verrait pas.
            { border: "1.5px solid var(--tcn-border)", color: "var(--tcn-ink)" }
      }
    >
      <Icone aria-hidden size={14} />
      {fiche ? "Fiche entière" : "Un résultat"}
    </span>
  );
}
