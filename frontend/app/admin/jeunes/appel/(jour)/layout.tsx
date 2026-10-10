import type { Metadata } from "next";
import type { ReactNode } from "react";
import { ecran } from "@/components/layout/nav.config";

// La page est un composant client : son titre de document vit ici (#1040).
// Groupe `(jour)` : ce titre ne doit pas coiffer `appel/[id]`, il y effacerait
// le gabarit `%s · TCN` (#1290).
export const metadata: Metadata = { title: ecran("/admin/jeunes/appel").title };

export default function Layout({ children }: { children: ReactNode }) {
  return children;
}
