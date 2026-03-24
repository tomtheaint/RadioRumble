/**
 * Add commas to a number: 1234 -> "1,234"
 */
export function formatNumber(n: number): string {
  return n.toLocaleString('en-US');
}

/**
 * Format an ISO timestamp to "HH:MM" UTC.
 */
export function formatTime(iso: string): string {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return '--:--';
  const h = d.getUTCHours().toString().padStart(2, '0');
  const m = d.getUTCMinutes().toString().padStart(2, '0');
  return `${h}:${m}`;
}

/**
 * Format a duration in seconds to a human-readable string.
 * >= 3600: "2h 15m"
 * < 3600:  "45m 30s"
 * < 60:    "30s"
 */
export function formatDuration(seconds: number): string {
  if (seconds < 0) seconds = 0;
  const s = Math.floor(seconds);

  if (s >= 3600) {
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    return m > 0 ? `${h}h ${m}m` : `${h}h`;
  }

  if (s >= 60) {
    const m = Math.floor(s / 60);
    const rem = s % 60;
    return rem > 0 ? `${m}m ${rem}s` : `${m}m`;
  }

  return `${s}s`;
}

/**
 * Uppercase and trim a callsign.
 */
export function formatCallsign(call: string): string {
  return call.trim().toUpperCase();
}

/**
 * Normalize a band string to "XXm" format.
 * Handles inputs like "20", "20m", "20M", " 20m ".
 */
export function formatBand(band: string): string {
  const b = band.trim().toLowerCase().replace(/m$/, '');
  return `${b}m`;
}
