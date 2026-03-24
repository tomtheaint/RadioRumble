import { Router } from 'express';

export default function statsRoutes(db) {
  const router = Router();

  // Aggregated leaderboard — total QSOs and points per station with band/mode breakdown
  router.get('/api/contests/:contestId/scoreboard', (req, res) => {
    try {
      const contestId = req.params.contestId;

      // Per-station totals
      const stations = db.prepare(`
        SELECT
          station_callsign,
          COUNT(*) AS qso_count,
          COALESCE(SUM(points), 0) AS total_points,
          COALESCE(SUM(is_multiplier), 0) AS multipliers,
          COALESCE(SUM(points), 0) * MAX(1, COALESCE(SUM(is_multiplier), 0)) AS score
        FROM qsos
        WHERE contest_id = ?
        GROUP BY station_callsign
        ORDER BY score DESC
      `).all(contestId);

      // Per-station band breakdown
      const bandRows = db.prepare(`
        SELECT station_callsign, band, COUNT(*) AS count
        FROM qsos WHERE contest_id = ? GROUP BY station_callsign, band
      `).all(contestId);

      // Per-station mode breakdown
      const modeRows = db.prepare(`
        SELECT station_callsign, mode, COUNT(*) AS count
        FROM qsos WHERE contest_id = ? GROUP BY station_callsign, mode
      `).all(contestId);

      // Operator → club mapping
      const operators = db.prepare(`
        SELECT o.callsign, c.name AS club_name
        FROM operators o JOIN clubs c ON o.club_id = c.id
        WHERE o.contest_id = ?
      `).all(contestId);
      const opClubMap = {};
      for (const op of operators) opClubMap[op.callsign] = op.club_name;

      // Build band/mode maps per station
      const bandMap = {};
      const modeMap = {};
      for (const r of bandRows) {
        if (!bandMap[r.station_callsign]) bandMap[r.station_callsign] = {};
        bandMap[r.station_callsign][r.band] = r.count;
      }
      for (const r of modeRows) {
        if (!modeMap[r.station_callsign]) modeMap[r.station_callsign] = {};
        modeMap[r.station_callsign][r.mode] = r.count;
      }

      // QSOs in last hour per station
      const rateRows = db.prepare(`
        SELECT station_callsign, COUNT(*) AS rate
        FROM qsos
        WHERE contest_id = ? AND created_at >= datetime('now', '-1 hour')
        GROUP BY station_callsign
      `).all(contestId);
      const rateMap = {};
      for (const r of rateRows) rateMap[r.station_callsign] = r.rate;

      // Assemble response matching frontend StationScore type
      const result = stations.map(s => ({
        callsign: s.station_callsign,
        clubName: opClubMap[s.station_callsign] || null,
        totalQsos: s.qso_count,
        totalPoints: s.total_points,
        bands: bandMap[s.station_callsign] || {},
        modes: modeMap[s.station_callsign] || {},
        rate: rateMap[s.station_callsign] || 0,
      }));

      // Club totals
      const clubTotals = db.prepare(`
        SELECT c.name AS club_name, COUNT(q.id) AS total_qsos, COALESCE(SUM(q.points), 0) AS total_points
        FROM clubs c
        LEFT JOIN operators o ON o.club_id = c.id AND o.contest_id = c.contest_id
        LEFT JOIN qsos q ON q.station_callsign = o.callsign AND q.contest_id = o.contest_id
        WHERE c.contest_id = ?
        GROUP BY c.name
        ORDER BY total_points DESC
      `).all(contestId);

      // Contest status
      const contest = db.prepare('SELECT status, start_time, end_time FROM contests WHERE id = ?').get(contestId);

      res.json({
        stations: result,
        clubTotals: clubTotals.map(c => ({
          clubName: c.club_name,
          totalQsos: c.total_qsos,
          totalPoints: c.total_points,
        })),
        contestStatus: contest?.status || 'pending',
        elapsed: contest?.start_time ? Math.floor((Date.now() - new Date(contest.start_time).getTime()) / 1000) : 0,
        remaining: contest?.end_time ? Math.max(0, Math.floor((new Date(contest.end_time).getTime() - Date.now()) / 1000)) : null,
      });
    } catch (err) {
      res.status(500).json({ error: err.message });
    }
  });

  // Full stats overview
  router.get('/api/contests/:contestId/stats', (req, res) => {
    try {
      const contestId = req.params.contestId;

      const totals = db.prepare(`
        SELECT
          COUNT(*) AS total_qsos,
          SUM(points) AS total_points,
          COUNT(DISTINCT station_callsign) AS unique_stations,
          COUNT(DISTINCT band) AS unique_bands,
          COUNT(DISTINCT mode) AS unique_modes
        FROM qsos WHERE contest_id = ?
      `).get(contestId);

      const topStations = db.prepare(`
        SELECT station_callsign, COUNT(*) AS qso_count, SUM(points) AS total_points
        FROM qsos WHERE contest_id = ?
        GROUP BY station_callsign ORDER BY total_points DESC LIMIT 10
      `).all(contestId);

      const bandBreakdown = db.prepare(`
        SELECT band, COUNT(*) AS count FROM qsos
        WHERE contest_id = ? GROUP BY band ORDER BY count DESC
      `).all(contestId);

      const modeBreakdown = db.prepare(`
        SELECT mode, COUNT(*) AS count FROM qsos
        WHERE contest_id = ? GROUP BY mode ORDER BY count DESC
      `).all(contestId);

      const grids = db.prepare(`
        SELECT DISTINCT UPPER(SUBSTR(gridsquare, 1, 4)) AS grid
        FROM qsos
        WHERE contest_id = ? AND gridsquare IS NOT NULL AND gridsquare != ''
      `).all(contestId).map(r => r.grid);

      res.json({ totals, topStations, bandBreakdown, modeBreakdown, grids });
    } catch (err) {
      res.status(500).json({ error: err.message });
    }
  });

  // QSOs per hour rate
  router.get('/api/contests/:contestId/stats/rate', (req, res) => {
    try {
      const rows = db.prepare(`
        SELECT
          qso_date,
          substr(time_on, 1, 2) AS hour,
          COUNT(*) AS count
        FROM qsos
        WHERE contest_id = ?
        GROUP BY qso_date, hour
        ORDER BY qso_date, hour
      `).all(req.params.contestId);
      res.json(rows);
    } catch (err) {
      res.status(500).json({ error: err.message });
    }
  });

  // Band distribution
  router.get('/api/contests/:contestId/stats/bands', (req, res) => {
    try {
      const rows = db.prepare(`
        SELECT band, COUNT(*) AS count FROM qsos
        WHERE contest_id = ? GROUP BY band ORDER BY count DESC
      `).all(req.params.contestId);
      res.json(rows);
    } catch (err) {
      res.status(500).json({ error: err.message });
    }
  });

  // Mode distribution
  router.get('/api/contests/:contestId/stats/modes', (req, res) => {
    try {
      const rows = db.prepare(`
        SELECT mode, COUNT(*) AS count FROM qsos
        WHERE contest_id = ? GROUP BY mode ORDER BY count DESC
      `).all(req.params.contestId);
      res.json(rows);
    } catch (err) {
      res.status(500).json({ error: err.message });
    }
  });

  // Map data — QSOs with grid coordinates
  router.get('/api/contests/:contestId/map-data', (req, res) => {
    try {
      const rows = db.prepare(`
        SELECT
          id, station_callsign, call, band, mode,
          gridsquare, my_gridsquare, qso_date, time_on, points
        FROM qsos
        WHERE contest_id = ? AND gridsquare IS NOT NULL
        ORDER BY qso_date DESC, time_on DESC
      `).all(req.params.contestId);

      // Convert Maidenhead grid squares to approximate lat/lng
      const mapped = rows.map(row => ({
        ...row,
        coordinates: gridToLatLng(row.gridsquare),
        stationCoordinates: row.my_gridsquare ? gridToLatLng(row.my_gridsquare) : null,
      }));

      res.json(mapped);
    } catch (err) {
      res.status(500).json({ error: err.message });
    }
  });

  return router;
}

/**
 * Convert a Maidenhead grid square to approximate lat/lng.
 * Supports 4- and 6-character locators.
 */
function gridToLatLng(grid) {
  if (!grid || grid.length < 4) return null;

  const upper = grid.toUpperCase();
  let lng = (upper.charCodeAt(0) - 65) * 20 - 180;
  let lat = (upper.charCodeAt(1) - 65) * 10 - 90;
  lng += parseInt(upper[2], 10) * 2;
  lat += parseInt(upper[3], 10);

  if (grid.length >= 6) {
    lng += (upper.charCodeAt(4) - 65) * (2 / 24);
    lat += (upper.charCodeAt(5) - 65) * (1 / 24);
  }

  // Center of the grid square
  if (grid.length >= 6) {
    lng += 1 / 24;
    lat += 0.5 / 24;
  } else {
    lng += 1;
    lat += 0.5;
  }

  return { lat, lng };
}
