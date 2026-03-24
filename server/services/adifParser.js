/**
 * ADIF (Amateur Data Interchange Format) parser.
 * Extracts field-value pairs from ADIF-encoded strings.
 */

const KNOWN_FIELDS = [
  'call', 'band', 'mode', 'frequency', 'rst_sent', 'rst_rcvd',
  'gridsquare', 'my_gridsquare', 'station_callsign',
  'qso_date', 'time_on', 'time_off',
];

const BAND_ALIASES = {
  '160m': '160m', '1.8': '160m',
  '80m': '80m', '3.5': '80m',
  '60m': '60m', '5': '60m',
  '40m': '40m', '7': '40m',
  '30m': '30m', '10.1': '30m',
  '20m': '20m', '14': '20m',
  '17m': '17m', '18': '17m',
  '15m': '15m', '21': '15m',
  '12m': '12m', '24': '12m',
  '10m': '10m', '28': '10m',
  '6m': '6m', '50': '6m',
  '2m': '2m', '144': '2m',
  '70cm': '70cm', '432': '70cm',
};

/**
 * Normalize a band value to standard form (e.g. "20m").
 * @param {string} raw
 * @returns {string|null}
 */
function normalizeBand(raw) {
  if (!raw) return null;
  const key = raw.trim().toLowerCase().replace(/\s+/g, '');
  return BAND_ALIASES[key] || key;
}

/**
 * Parse an ADIF-formatted string into an object of known fields.
 *
 * ADIF field format: <field:length>value
 * Example: <call:6>KB0KRU <gridsquare:4>EN12 <mode:3>FT8
 *
 * @param {string} adifString - Raw ADIF text
 * @returns {Object} Parsed record with known field keys; missing fields are null
 */
export function parseAdif(adifString) {
  const result = {};
  for (const field of KNOWN_FIELDS) {
    result[field] = null;
  }

  if (!adifString || typeof adifString !== 'string') {
    return result;
  }

  const regex = /<(\w+):(\d+)>([^<]*)/g;
  let match;

  while ((match = regex.exec(adifString)) !== null) {
    const fieldName = match[1].toLowerCase();
    const length = parseInt(match[2], 10);
    const rawValue = match[3].substring(0, length).trim();

    if (KNOWN_FIELDS.includes(fieldName)) {
      if (fieldName === 'band') {
        result.band = normalizeBand(rawValue);
      } else {
        result[fieldName] = rawValue || null;
      }
    }
  }

  return result;
}
