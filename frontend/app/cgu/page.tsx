import type { Metadata } from "next";
import { LegalPage } from "@/components/legal/LegalPage";
import { TERMS_OF_USE } from "@/components/legal/content/cgu";

export const metadata: Metadata = { title: TERMS_OF_USE.title };

/** Hors du groupe gardé (#333), comme les deux autres textes légaux. */
export default function CguPage() {
  return <LegalPage document={TERMS_OF_USE} />;
}
