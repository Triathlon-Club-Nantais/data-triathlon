import type { Metadata } from "next";
import type { ReactNode } from "react";

// La page est un composant client : son titre de document vit ici (#1040).
export const metadata: Metadata = { title: "Carte des épreuves" };

export default function Layout({ children }: { children: ReactNode }) {
  return children;
}
