import type { ReactNode } from "react";
import { spaceRefusal } from "@/components/layout/space-guard";

/** Tout connecté y a accès : la garde ne fait que renvoyer un anonyme vers `/login` (#1663). */
export default async function AccountLayout({ children }: { children: ReactNode }) {
  const refus = await spaceRefusal("Mon compte", () => true, null);
  if (refus) return refus;
  return children;
}
