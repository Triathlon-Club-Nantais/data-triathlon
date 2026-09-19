import { Card } from "@/components/tcn/Card";
import type { GuideSection } from "./types";

/** Table des matières : un lien d'ancre par section, dans l'ordre fourni. */
export function GuideSommaire({ sections }: { sections: GuideSection[] }) {
  return (
    <Card variant="dashed" padding={20}>
      <nav aria-label="Sommaire du guide">
        <ul className="grid gap-2 sm:grid-cols-2">
          {sections.map((section) => (
            <li key={section.id}>
              <a
                href={`#${section.id}`}
                // `--tcn-orange` sur `--tcn-surface` ne tient que 3,68:1 en
                // texte courant (sous 4,5:1, WCAG 1.4.3) — `-deep` descend
                // à 4,84:1, même arbitrage que `Badge.tsx`/`.tcn-btn`
                // (revue UI/UX, #865).
                className="text-sm font-medium text-[var(--tcn-orange-deep)] underline-offset-4 hover:underline"
              >
                {section.titre}
              </a>
            </li>
          ))}
        </ul>
      </nav>
    </Card>
  );
}
