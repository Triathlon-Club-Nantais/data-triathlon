const MAX_TENTHS = 864000;

// ss[,d] | m:ss[,d] | h:mm:ss[,d] ; groups: hours?, minutes?, seconds, tenth?
const FORMS = [
  /^()()(\d{1,5})(?:[.,](\d))?$/,
  /^()(\d{1,4}):([0-5]\d)(?:[.,](\d))?$/,
  /^(\d{1,2}):([0-5]\d):([0-5]\d)(?:[.,](\d))?$/,
];

/** Parse a typed duration into tenths of a second, or null when malformed. */
export function parseDuration(text: string): number | null {
  const trimmed = text.trim();
  for (const form of FORMS) {
    const match = form.exec(trimmed);
    if (!match) continue;
    const [, hours, minutes, seconds, tenth] = match;
    const total =
      (Number(hours || 0) * 3600 + Number(minutes || 0) * 60 + Number(seconds)) * 10 +
      Number(tenth || 0);
    return total >= 1 && total <= MAX_TENTHS ? total : null;
  }
  return null;
}

/** Format tenths of a second: "42,3 s", "7:42,3", "1:02:05". */
export function formatDuration(tenths: number): string {
  const decimal = tenths % 10 ? `,${tenths % 10}` : "";
  const totalSeconds = Math.floor(tenths / 10);
  if (totalSeconds < 60) return `${totalSeconds}${decimal} s`;
  const seconds = String(totalSeconds % 60).padStart(2, "0");
  const minutes = Math.floor(totalSeconds / 60) % 60;
  const hours = Math.floor(totalSeconds / 3600);
  if (hours > 0) return `${hours}:${String(minutes).padStart(2, "0")}:${seconds}${decimal}`;
  return `${minutes}:${seconds}${decimal}`;
}
