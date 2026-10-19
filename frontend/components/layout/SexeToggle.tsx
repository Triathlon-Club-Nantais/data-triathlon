"use client";
import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { useTransition } from "react";
import { SegmentedControl } from "@/components/tcn/SegmentedControl";
import { SEXE_PARAM, genderFromSexeParam } from "@/lib/scope";

const OPTIONS = [
  { value: "", label: "Tous" },
  { value: "H", label: "Hommes" },
  { value: "F", label: "Femmes" },
];

/** Filtre par sexe d'une page : pilote `?sexe=H|F` et remet la pagination à zéro. */
export function SexeToggle() {
  const router = useRouter();
  const pathname = usePathname();
  const sp = useSearchParams();
  const [pending, startTransition] = useTransition();
  const sexe = sp.get(SEXE_PARAM);
  const current = genderFromSexeParam(sexe) ? (sexe as string) : "";

  function setSexe(value: string) {
    const params = new URLSearchParams(sp.toString());
    if (value) params.set(SEXE_PARAM, value);
    else params.delete(SEXE_PARAM);
    params.delete("page");
    const qs = params.toString();
    startTransition(() => router.push(`${pathname}${qs ? `?${qs}` : ""}`));
  }

  return (
    <div role="group" aria-label="Sexe" data-pending={pending || undefined} className="data-pending:opacity-70">
      <SegmentedControl options={OPTIONS} value={current} onChange={setSexe} />
    </div>
  );
}
