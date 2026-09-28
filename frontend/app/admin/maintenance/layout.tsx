import type { Metadata } from "next";
import type { ReactNode } from "react";
import { ecran } from "@/components/layout/nav.config";

// La page est un composant client : son titre de document vit ici (#1040).
export const metadata: Metadata = { title: ecran("/admin/maintenance").title };

export default function Layout({ children }: { children: ReactNode }) {
  return children;
}
