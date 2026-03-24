/**
 * Convert a Maidenhead grid locator to latitude/longitude (center of square).
 * Supports 4-char (e.g. "EM28") and 6-char (e.g. "EM28iv") grids.
 */
export function gridToLatLon(grid: string): { lat: number; lng: number } | null {
  if (!grid || typeof grid !== 'string') return null;

  const g = grid.trim();
  if (g.length !== 4 && g.length !== 6) return null;

  const field1 = g.charCodeAt(0);
  const field2 = g.charCodeAt(1);
  const square1 = g.charCodeAt(2);
  const square2 = g.charCodeAt(3);

  // Field: A-R (uppercase)
  const A = 65;
  const R = 82;
  if (field1 < A || field1 > R) return null;
  if (field2 < A || field2 > R) return null;

  // Square: 0-9
  const ZERO = 48;
  const NINE = 57;
  if (square1 < ZERO || square1 > NINE) return null;
  if (square2 < ZERO || square2 > NINE) return null;

  let lng = (field1 - A) * 20 - 180;
  let lat = (field2 - A) * 10 - 90;

  lng += (square1 - ZERO) * 2;
  lat += (square2 - ZERO) * 1;

  if (g.length === 6) {
    const sub1 = g.charCodeAt(4);
    const sub2 = g.charCodeAt(5);

    // Subsquare: a-x (lowercase)
    const a = 97;
    const x = 120;
    // Accept both upper and lower case for subsquare
    const s1 = sub1 >= A && sub1 <= 88 ? sub1 - A : sub1 >= a && sub1 <= x ? sub1 - a : -1;
    const s2 = sub2 >= A && sub2 <= 88 ? sub2 - A : sub2 >= a && sub2 <= x ? sub2 - a : -1;

    if (s1 < 0 || s1 > 23 || s2 < 0 || s2 > 23) return null;

    lng += s1 * (2 / 24);
    lat += s2 * (1 / 24);

    // Center of subsquare
    lng += 1 / 24;
    lat += 0.5 / 24;
  } else {
    // Center of 4-char grid square
    lng += 1;
    lat += 0.5;
  }

  return { lat, lng };
}
