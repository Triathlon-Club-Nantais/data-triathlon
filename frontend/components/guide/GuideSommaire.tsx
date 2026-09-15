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
                className="text-sm font-medium text-[var(--tcn-orange)] underline-offset-4 hover:underline"
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
