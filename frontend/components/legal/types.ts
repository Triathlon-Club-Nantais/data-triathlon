import type { ReactNode } from "react";

/** Une rubrique d'un texte légal. */
export type LegalSection = {
  /** Slug utilisé comme ancre, unique dans son document. */
  id: string;
  title: string;
  content: ReactNode;
};

/** Un texte légal versionné dans le dépôt (#333). */
export type LegalDocument = {
  title: string;
  description: string;
  /** Date ISO `YYYY-MM-DD`, à changer dans le même commit que le texte. */
  updatedAt: string;
  sections: LegalSection[];
};
