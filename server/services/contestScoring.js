/**
 * Contest scoring engine.
 *
 * Default rules: 1 point per QSO, multipliers for unique grid squares.
 * A rules object can override point values per band or mode.
 */

/**
 * Calculate the point value of a single QSO.
 *
 * @param {Object} qso - Parsed QSO record (from adifParser)
 * @param {Object} [rules] - Optional scoring rules
 * @param {number} [rules.defaultPoints=1] - Base points per QSO
 * @param {Object.<string, number>} [rules.bandPoints] - Points by band (e.g. { "40m": 2 })
 * @param {Object.<string, number>} [rules.modePoints] - Points by mode (e.g. { "CW": 3 })
 * @returns {number} Point value for this QSO
 */
export function calculatePoints(qso, rules = {}) {
  if (!qso) return 0;

  const defaultPoints = rules.defaultPoints ?? 1;

  // Band-specific override takes precedence
  if (rules.bandPoints && qso.band && rules.bandPoints[qso.band] != null) {
    return rules.bandPoints[qso.band];
  }

  // Mode-specific override
  if (rules.modePoints && qso.mode && rules.modePoints[qso.mode] != null) {
    return rules.modePoints[qso.mode];
  }

  return defaultPoints;
}

/**
 * Check whether a QSO represents a new multiplier.
 *
 * A multiplier is awarded for:
 *   - A grid square not yet worked (based on gridsquare field)
 *   - A DXCC entity not yet worked (based on call prefix — simplified)
 *
 * @param {Object} qso - The new QSO to evaluate
 * @param {Object[]} existingQsos - Array of previously logged QSOs
 * @returns {{isNew: boolean, type: string|null, value: string|null}}
 */
export function isMultiplier(qso, existingQsos = []) {
  if (!qso) {
    return { isNew: false, type: null, value: null };
  }

  // Check unique grid square (4-char prefix for multiplier purposes)
  if (qso.gridsquare) {
    const grid4 = qso.gridsquare.substring(0, 4).toUpperCase();
    const gridSeen = existingQsos.some(
      (q) => q.gridsquare && q.gridsquare.substring(0, 4).toUpperCase() === grid4
    );
    if (!gridSeen) {
      return { isNew: true, type: 'grid', value: grid4 };
    }
  }

  // Check unique DXCC (simplified: use callsign prefix before the digit group)
  if (qso.call) {
    const prefix = extractDxccPrefix(qso.call);
    if (prefix) {
      const prefixSeen = existingQsos.some(
        (q) => q.call && extractDxccPrefix(q.call) === prefix
      );
      if (!prefixSeen) {
        return { isNew: true, type: 'dxcc', value: prefix };
      }
    }
  }

  return { isNew: false, type: null, value: null };
}

/**
 * Extract a simplified DXCC prefix from a callsign.
 * Takes everything up to and including the first digit sequence.
 *
 * @param {string} call
 * @returns {string|null}
 */
function extractDxccPrefix(call) {
  if (!call) return null;
  const match = call.match(/^([A-Z0-9]*\d)/i);
  return match ? match[1].toUpperCase() : null;
}
