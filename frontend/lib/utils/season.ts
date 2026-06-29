// Miroir des helpers backend `app/core/season.py`. Saison = 1ᵉʳ sept Y → 31 août Y+1.
// Duplication assumée (le front ne partage pas de code Python) ; couverte par tests de bornes.

/** Année de début de la saison contenant la date ISO « YYYY-MM-DD ». */
export function seasonOf(iso: string): number {
  const year = Number(iso.slice(0, 4));
  const month = Number(iso.slice(5, 7));
  return month >= 9 ? year : year - 1;
}

/** Saison en cours (bascule au 1ᵉʳ septembre). `now` injectable pour les tests.
 *  Getters UTC pour rester miroir du backend (`utcnow()`) et éviter tout
 *  mismatch SSR/hydratation autour du 1ᵉʳ septembre selon le fuseau local. */
export function currentSeason(now: Date = new Date()): number {
  const year = now.getUTCFullYear();
  const month = now.getUTCMonth() + 1;
  return month >= 9 ? year : year - 1;
}

/** Libellé d'affichage « Saison Y — Y+1 ». */
export function seasonLabel(startYear: number): string {
  return `Saison ${startYear} — ${startYear + 1}`;
}

/** Parse un CSV d'années (« 2025,2023 ») : tolère espaces, ignore non entiers, dédoublonne. */
export function parseSeasonsParam(raw?: string | null): number[] {
  if (!raw) return [];
  const out: number[] = [];
  for (const token of raw.split(",")) {
    const trimmed = token.trim();
    if (!trimmed) continue;
    const year = Number(trimmed);
    if (!Number.isInteger(year)) continue;
    if (!out.includes(year)) out.push(year);
  }
  return out;
}

/** Sérialise une liste d'années en CSV. */
export function serializeSeasons(years: number[]): string {
  return years.join(",");
}

/** Ajoute/retire une saison de la sélection (toggle). */
export function toggleSeason(selected: number[], year: number): number[] {
  return selected.includes(year)
    ? selected.filter((y) => y !== year)
    : [...selected, year];
}

/** Libellé de l'en-tête : 1 saison → libellé complet ; plusieurs → décompte. */
export function seasonSelectionLabel(years: number[]): string {
  if (years.length === 0) return seasonLabel(currentSeason());
  if (years.length === 1) return seasonLabel(years[0]);
  return `${years.length} saisons sélectionnées`;
}
