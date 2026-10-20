"use client";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { hrefSansSexe } from "@/lib/scope";

/** Sortie des états vides filtrés par sexe : la même page, `?sexe=` retiré. */
export function RetirerFiltreSexe({ label = "Retirer le filtre par sexe" }: { label?: string }) {
  const pathname = usePathname();
  const sp = useSearchParams();
  return (
    <Link
      href={hrefSansSexe(pathname, sp)}
      className="tcn-cible-tactile mt-3 inline-flex items-center text-sm font-semibold text-accent-ink hover:underline"
    >
      {label}
    </Link>
  );
}
