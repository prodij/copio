/** "3h 20m", "45s", "2d 4h": the two largest units. */
export function duration(seconds: number): string {
  const s = Math.max(0, Math.round(seconds));
  const units: [string, number][] = [["d", 86_400], ["h", 3_600], ["m", 60], ["s", 1]];
  const parts: string[] = [];
  let rest = s;
  for (const [label, size] of units) {
    const n = Math.floor(rest / size);
    if (n > 0 || (label === "s" && parts.length === 0)) parts.push(`${n}${label}`);
    rest -= n * size;
    if (parts.length === 2) break;
  }
  return parts.join(" ");
}

/** "5m ago" relative to `now`: seconds only under a minute. A full timestamp goes in the title. */
export function ago(iso: string, now: number = Date.now()): string {
  const s = (now - new Date(iso).getTime()) / 1000;
  return `${duration(s >= 60 ? Math.floor(s / 60) * 60 : s)} ago`;
}

/** Full date and time, for titles and details. */
export function when(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

/** Compact: "Nov 25, 3:23 PM"; the year only when it isn't this one. */
export function short(iso: string, now: Date = new Date()): string {
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
    ...(d.getFullYear() !== now.getFullYear() ? { year: "numeric" } : {}),
  });
}

export function label(value: string): string {
  return value.replaceAll("_", " ");
}
