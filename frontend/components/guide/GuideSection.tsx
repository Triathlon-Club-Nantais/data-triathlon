import Image from "next/image";
import { Badge, Card } from "@/components/tcn";
import type { GuideSection as GuideSectionData } from "./types";

export function GuideSection({ section }: { section: GuideSectionData }) {
  return (
    <Card
      id={section.id}
      // `scroll-margin-top` : l'ancre ne se retrouve pas masquée sous la nav
      // fixe quand on y accède directement (#865, US3). Valeur en dur : la
      // barre mobile sticky fait ~60px, cette marge la couvre largement (le
      // rail desktop n'est pas une barre du haut, la marge y est juste un
      // espace inoffensif) — pas de token `--tcn-nav-height` dans le
      // design system à référencer (revue UI/UX, #865).
      style={{ scrollMarginTop: "80px" }}
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
          <div key={capture.src} className="space-y-2">
            {capture.placeholder && <Badge variant="orange">Capture à venir</Badge>}
            <Image
              src={capture.src}
              // Le statut "à venir" est répété dans l'alt : le badge visuel
              // ne suffit pas pour un lecteur d'écran, qui n'a que le texte
              // alternatif de l'image (#865, revue de code).
              alt={capture.placeholder ? `Capture à venir — ${capture.alt}` : capture.alt}
              // Ratio réel des 21 captures livrées (1418×840) : sans ce
              // ratio exact, `width`/`height` imposent une boîte 1200×750
              // (1,6:1) que le navigateur étire, ~5,5 % de distorsion sur
              // chaque image (revue UI/UX, #865).
              width={1418}
              height={840}
              style={{ width: "100%", height: "auto", borderRadius: "var(--tcn-radius-2xl)" }}
              className="border border-[var(--tcn-border)]"
            />
          </div>
        ))}
      </div>
    </Card>
  );
}
