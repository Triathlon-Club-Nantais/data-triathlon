import { PageHeader } from "@/components/layout/PageHeader";
import { PageShell } from "@/components/layout/PageShell";
import { Card } from "@/components/tcn/Card";
import type { LegalDocument } from "./types";

const TOC_THRESHOLD = 4;

function longDate(isoDate: string): string {
  const [year, month, day] = isoDate.split("-").map(Number);
  return new Date(year, month - 1, day).toLocaleDateString("fr-FR", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

/** Gabarit commun des trois textes légaux (#333). */
export function LegalPage({ document }: { document: LegalDocument }) {
  return (
    <PageShell>
      <div className="space-y-6">
        <PageHeader eyebrow="Informations légales" title={document.title} description={document.description} />
        <p className="text-sm text-[var(--tcn-text-faint)]">
          Dernière mise à jour : <time dateTime={document.updatedAt}>{longDate(document.updatedAt)}</time>
        </p>
        {document.sections.length > TOC_THRESHOLD && (
          <Card variant="dashed" padding={20}>
            <nav aria-label="Sommaire">
              <ul className="grid gap-2 sm:grid-cols-2">
                {document.sections.map((section) => (
                  <li key={section.id}>
                    <a
                      href={`#${section.id}`}
                      // `-deep` : 4,57:1 sur `--tcn-surface`, l'orange simple n'y tient que 3,68:1.
                      className="text-sm font-medium text-[var(--tcn-orange-deep)] underline-offset-4 hover:underline"
                    >
                      {section.title}
                    </a>
                  </li>
                ))}
              </ul>
            </nav>
          </Card>
        )}
        <div className="space-y-6">
          {document.sections.map((section) => (
            <Card key={section.id} id={section.id} style={{ scrollMarginTop: "80px" }} className="space-y-3">
              <h2 className="font-heading text-xl tracking-tight text-foreground">{section.title}</h2>
              <div className="space-y-3 text-sm leading-relaxed text-foreground">{section.content}</div>
            </Card>
          ))}
        </div>
      </div>
    </PageShell>
  );
}
