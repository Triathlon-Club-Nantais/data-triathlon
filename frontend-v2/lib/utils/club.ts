const TCN_KEYWORDS = ["nantais", "tcn", "triathlon club nant"];

export function isTCN(club: string | null | undefined): boolean {
  if (!club) return false;
  const low = club.toLowerCase();
  return TCN_KEYWORDS.some((k) => low.includes(k));
}
