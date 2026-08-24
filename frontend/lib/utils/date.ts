export function formatDate(d: string | null | undefined): string {
  if (!d) return "";
  const m = String(d).match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (m) return new Date(+m[1], +m[2] - 1, +m[3]).toLocaleDateString("fr-FR");
  return String(d);
}

/**
 * Date **et** heure. `formatDate` coupe l'horodatage au jour : deux
 * événements du même jour y deviennent indiscernables.
 */
export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  return d.toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" });
}

export function formatMonth(ym: string | null | undefined): string {
  if (!ym) return "";
  const m = String(ym).match(/^(\d{4})-(\d{2})/);
  if (!m) return String(ym);
  return new Date(+m[1], +m[2] - 1, 1).toLocaleDateString("fr-FR", {
    month: "long",
    year: "numeric",
  });
}

export function formatMonthShort(ym: string | null | undefined): string {
  if (!ym) return "";
  const m = String(ym).match(/^(\d{4})-(\d{2})/);
  if (!m) return String(ym);
  return new Date(+m[1], +m[2] - 1, 1)
    .toLocaleDateString("fr-FR", { month: "short" })
    .replace(".", "");
}

export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return "";
  const ts = new Date(iso).getTime();
  if (Number.isNaN(ts)) return "";

  const diff = Date.now() - ts;
  const days = Math.floor(diff / 86400000);
  if (days <= 0) return "aujourd'hui";
  if (days === 1) return "hier";
  if (days < 30) return `il y a ${days} j`;
  if (days < 365) return `il y a ${Math.floor(days / 30)} mois`;
  const years = Math.floor(days / 365);
  return `il y a ${years} an${years > 1 ? "s" : ""}`;
}
