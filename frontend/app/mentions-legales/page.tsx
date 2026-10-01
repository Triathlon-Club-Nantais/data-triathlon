import type { Metadata } from "next";
import { LegalPage } from "@/components/legal/LegalPage";
import { LEGAL_NOTICE } from "@/components/legal/content/mentions-legales";

export const metadata: Metadata = { title: LEGAL_NOTICE.title };

/** Hors du groupe gardé (#333), comme les deux autres textes légaux. */
export default function MentionsLegalesPage() {
  return <LegalPage document={LEGAL_NOTICE} />;
}
