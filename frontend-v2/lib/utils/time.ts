/** Convertit "HH:MM:SS" ou "MM:SS" en secondes ; null si invalide. */
/** Convertit "HH:MM:SS" ou "MM:SS" en secondes ; null si invalide. */
export function secondsFromHms(value: string | null | undefined): number | null {
  if (!value) return null;

  // HH est optionnel. Exemples acceptés : "2:30", "01:02:03".
  const m = value.match(/^(?:(?<hh>\d+):)?(?<mm>\d{1,2}):(?<ss>\d{2})$/);
  if (!m || !m.groups) return null;

  const hh = m.groups.hh ? Number(m.groups.hh) : 0;
  const mm = Number(m.groups.mm);
  const ss = Number(m.groups.ss);

  if ([hh, mm, ss].some((n) => Number.isNaN(n))) return null;
  if (mm >= 60 || ss >= 60) return null;

  return hh * 3600 + mm * 60 + ss;
}
