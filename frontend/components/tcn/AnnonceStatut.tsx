/**
 * Région `role="status"` visuellement masquée, partagée par les zones dont le
 * contenu change sans déplacer le focus (filtre, tri, bascule, import) —
 * sans elle, WCAG 4.1.3 (#477) : un lecteur d'écran ne signale ni le nouveau
 * décompte ni la fin d'un import. Patron initial : `AthleteSeasonList.tsx`.
 */
export function AnnonceStatut({ texte, busy }: { texte: string; busy?: boolean }) {
  return (
    <p className="sr-only" role="status" aria-live="polite" aria-atomic="true" aria-busy={busy}>
      {texte}
    </p>
  );
}
