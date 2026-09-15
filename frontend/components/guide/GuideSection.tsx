import Image from "next/image";
import { Card } from "@/components/tcn/Card";
import type { GuideSection as GuideSectionData } from "./types";

export function GuideSection({ section }: { section: GuideSectionData }) {
  return (
    <Card
      id={section.id}
      // `scroll-margin-top` : l'ancre ne se retrouve pas masquée sous la nav
      // fixe quand on y accède directement (#865, US3).
      style={{ scrollMarginTop: "calc(var(--tcn-nav-height, 64px) + 16px)" }}
      className="space-y-4"
    >
      <h2 className="font-heading text-xl tracking-tight text-foreground">{section.titre}</h2>
      <p className="text-sm text-[var(--tcn-text-faint)]">{section.casUsage}</p>
      <ol className="list-decimal space-y-1.5 pl-5 text-sm text-foreground">
        {section.etapes.map((etape, index) => (
          // Les étapes sont un contenu éditorial statique, sans identifiant
          // plus stable que leur position.
          <li key={index}>{etape}</li>
        ))}
      </ol>
      <div className="space-y-3">
        {section.captures.map((capture) => (
          <Image
            key={capture.src}
            src={capture.src}
            alt={capture.alt}
            width={1200}
            height={750}
            style={{ width: "100%", height: "auto", borderRadius: "var(--tcn-radius-2xl)" }}
            className="border border-[var(--tcn-border)]"
          />
        ))}
      </div>
    </Card>
  );
}
