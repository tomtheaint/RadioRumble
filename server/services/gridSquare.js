/**
 * Maidenhead grid square conversions.
 */

const GRID_4_RE = /^[A-Ra-r]{2}\d{2}$/;
const GRID_6_RE = /^[A-Ra-r]{2}\d{2}[A-Xa-x]{2}$/;

/**
 * Convert a 4- or 6-character Maidenhead grid locator to lat/lng center point.
 *
 * @param {string} grid - Maidenhead locator (4 or 6 chars)
 * @returns {{lat: number, lng: number}|null} Center of the grid square, or null if invalid
 */
export function gridToLatLon(grid) {
  if (!grid || typeof grid !== 'string') return null;
  grid = grid.trim();

  if (!GRID_4_RE.test(grid) && !GRID_6_RE.test(grid)) return null;

  const upper = grid.toUpperCase();

  // Field (first pair): A-R mapped to 0-17, each = 20 deg lng / 10 deg lat
  const lngField = (upper.charCodeAt(0) - 65) * 20;
  const latField = (upper.charCodeAt(1) - 65) * 10;

  // Square (second pair): 0-9, each = 2 deg lng / 1 deg lat
  const lngSquare = parseInt(upper[2], 10) * 2;
  const latSquare = parseInt(upper[3], 10) * 1;

  let lng = lngField + lngSquare - 180;
  let lat = latField + latSquare - 90;

  if (upper.length === 6) {
    // Subsquare (third pair): A-X mapped to 0-23, each = 5/60 deg lng / 2.5/60 deg lat
    const lngSub = (upper.charCodeAt(4) - 65) * (5 / 60);
    const latSub = (upper.charCodeAt(5) - 65) * (2.5 / 60);

    lng += lngSub + (5 / 120);   // center of subsquare
    lat += latSub + (2.5 / 120);
  } else {
    // Center of 4-char square
    lng += 1;   // half of 2 deg
    lat += 0.5; // half of 1 deg
  }

  return {
    lat: Math.round(lat * 1e6) / 1e6,
    lng: Math.round(lng * 1e6) / 1e6,
  };
}

/**
 * Convert latitude/longitude to a 6-character Maidenhead grid locator.
 *
 * @param {number} lat - Latitude (-90 to 90)
 * @param {number} lng - Longitude (-180 to 180)
 * @returns {string|null} 6-char Maidenhead locator, or null if inputs invalid
 */
export function latLonToGrid(lat, lng) {
  if (typeof lat !== 'number' || typeof lng !== 'number') return null;
  if (lat < -90 || lat > 90 || lng < -180 || lng > 180) return null;

  // Shift to positive range
  let adjLng = lng + 180;
  let adjLat = lat + 90;

  // Field
  const lngField = Math.floor(adjLng / 20);
  const latField = Math.floor(adjLat / 10);
  adjLng -= lngField * 20;
  adjLat -= latField * 10;

  // Square
  const lngSquare = Math.floor(adjLng / 2);
  const latSquare = Math.floor(adjLat / 1);
  adjLng -= lngSquare * 2;
  adjLat -= latSquare * 1;

  // Subsquare
  const lngSub = Math.floor(adjLng / (5 / 60));
  const latSub = Math.floor(adjLat / (2.5 / 60));

  return (
    String.fromCharCode(65 + lngField) +
    String.fromCharCode(65 + latField) +
    lngSquare.toString() +
    latSquare.toString() +
    String.fromCharCode(97 + Math.min(lngSub, 23)) +
    String.fromCharCode(97 + Math.min(latSub, 23))
  );
}
