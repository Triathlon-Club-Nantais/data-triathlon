import type { Metadata } from "next";
import { LegalPage } from "@/components/legal/LegalPage";
import { PRIVACY_POLICY } from "@/components/legal/content/confidentialite";

export const metadata: Metadata = { title: PRIVACY_POLICY.title };

/** Hors du groupe gardé (#333) : un non-adhérent n'a pas le code d'accès. */
export default function ConfidentialitePage() {
  return <LegalPage document={PRIVACY_POLICY} />;
}
