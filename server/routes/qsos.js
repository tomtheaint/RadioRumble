import { Router } from 'express';

export default function qsoRoutes(db) {
  const router = Router();

  // Recent 50 QSOs (must be before the generic :contestId/qsos route)
  router.get('/api/contests/:contestId/qsos/recent', (req, res) => {
    try {
      const rows = db.prepare(
        'SELECT * FROM qsos WHERE contest_id = ? ORDER BY created_at DESC LIMIT 50'
      ).all(req.params.contestId);
      res.json(rows);
    } catch (err) {
      res.status(500).json({ error: err.message });
    }
  });

  // List QSOs with optional filters and pagination
  router.get('/api/contests/:contestId/qsos', (req, res) => {
    const { limit = '100', offset = '0', band, mode, station } = req.query;

    let sql = 'SELECT * FROM qsos WHERE contest_id = ?';
    const params = [req.params.contestId];

    if (band) {
      sql += ' AND band = ?';
      params.push(band);
    }
    if (mode) {
      sql += ' AND mode = ?';
      params.push(mode);
    }
    if (station) {
      sql += ' AND station_callsign = ?';
      params.push(station);
    }

    sql += ' ORDER BY qso_date DESC, time_on DESC LIMIT ? OFFSET ?';
    params.push(parseInt(limit, 10), parseInt(offset, 10));

    try {
      const rows = db.prepare(sql).all(...params);
      res.json(rows);
    } catch (err) {
      res.status(500).json({ error: err.message });
    }
  });

  // Manually add QSO
  router.post('/api/contests/:contestId/qsos', (req, res) => {
    const {
      station_callsign, call, band, mode, frequency,
      rst_sent, rst_rcvd, gridsquare, my_gridsquare,
      qso_date, time_on, time_off, points, is_multiplier, raw_adif,
    } = req.body;

    if (!station_callsign || !call) {
      return res.status(400).json({ error: 'station_callsign and call are required' });
    }

    try {
      const info = db.prepare(`
        INSERT INTO qsos (
          contest_id, station_callsign, call, band, mode, frequency,
          rst_sent, rst_rcvd, gridsquare, my_gridsquare,
          qso_date, time_on, time_off, points, is_multiplier, raw_adif
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      `).run(
        req.params.contestId,
        station_callsign, call,
        band || null, mode || null, frequency || null,
        rst_sent || null, rst_rcvd || null,
        gridsquare || null, my_gridsquare || null,
        qso_date || null, time_on || null, time_off || null,
        points ?? 1, is_multiplier ?? 0,
        raw_adif || null
      );
      const qso = db.prepare('SELECT * FROM qsos WHERE id = ?').get(info.lastInsertRowid);
      res.status(201).json(qso);
    } catch (err) {
      res.status(500).json({ error: err.message });
    }
  });

  return router;
}
