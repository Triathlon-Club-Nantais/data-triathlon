"use client";
import { useEffect, useState } from "react";
import { formatCount } from "@/lib/utils/format";

const DUREE_MS = 900;

/** Monte de 0 à `valeur` au premier affichage ; valeur finale directe sous `prefers-reduced-motion`. */
export function ChiffreAnime({ valeur }: { valeur: number }) {
  const [affiche, setAffiche] = useState(valeur);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches || valeur === 0) return;
    let debut: number | null = null;
    let frame = 0;
    frame = requestAnimationFrame(function pas(maintenant) {
      debut ??= maintenant;
      const t = Math.min(1, (maintenant - debut) / DUREE_MS);
      setAffiche(Math.round(valeur * (1 - (1 - t) ** 3)));
      if (t < 1) frame = requestAnimationFrame(pas);
    });
    return () => cancelAnimationFrame(frame);
  }, [valeur]);

  if (affiche === valeur) return <>{formatCount(valeur)}</>;
  return (
    <>
      <span aria-hidden="true">{formatCount(affiche)}</span>
      <span className="sr-only">{formatCount(valeur)}</span>
    </>
  );
}
