import { Router } from 'express';

export default function clubRoutes(db) {
  const router = Router();

  // List clubs in contest
  router.get('/api/contests/:contestId/clubs', (req, res) => {
    try {
      const clubs = db.prepare(
        'SELECT * FROM clubs WHERE contest_id = ? ORDER BY name'
      ).all(req.params.contestId);

      // Attach operators to each club
      const getOperators = db.prepare('SELECT * FROM operators WHERE club_id = ?');
      const result = clubs.map(club => ({
        ...club,
        operators: getOperators.all(club.id),
      }));

      res.json(result);
    } catch (err) {
      res.status(500).json({ error: err.message });
    }
  });

  // Add club to contest
  router.post('/api/contests/:contestId/clubs', (req, res) => {
    const { name, callsign } = req.body;
    if (!name || !callsign) {
      return res.status(400).json({ error: 'name and callsign are required' });
    }
    try {
      const info = db.prepare(
        'INSERT INTO clubs (name, callsign, contest_id) VALUES (?, ?, ?)'
      ).run(name, callsign, req.params.contestId);
      const club = db.prepare('SELECT * FROM clubs WHERE id = ?').get(info.lastInsertRowid);
      res.status(201).json(club);
    } catch (err) {
      res.status(500).json({ error: err.message });
    }
  });

  // Update club
  router.patch('/api/clubs/:id', (req, res) => {
    const club = db.prepare('SELECT * FROM clubs WHERE id = ?').get(req.params.id);
    if (!club) return res.status(404).json({ error: 'Club not found' });

    const fields = [];
    const values = [];

    for (const col of ['name', 'callsign']) {
      if (req.body[col] !== undefined) {
        fields.push(`${col} = ?`);
        values.push(req.body[col]);
      }
    }

    if (fields.length === 0) {
      return res.status(400).json({ error: 'No valid fields to update' });
    }

    try {
      values.push(req.params.id);
      db.prepare(`UPDATE clubs SET ${fields.join(', ')} WHERE id = ?`).run(...values);
      const updated = db.prepare('SELECT * FROM clubs WHERE id = ?').get(req.params.id);
      res.json(updated);
    } catch (err) {
      res.status(500).json({ error: err.message });
    }
  });

  // Delete club
  router.delete('/api/clubs/:id', (req, res) => {
    try {
      const info = db.prepare('DELETE FROM clubs WHERE id = ?').run(req.params.id);
      if (info.changes === 0) return res.status(404).json({ error: 'Club not found' });
      res.json({ ok: true });
    } catch (err) {
      res.status(500).json({ error: err.message });
    }
  });

  // Add operator to club
  router.post('/api/clubs/:clubId/operators', (req, res) => {
    const { callsign } = req.body;
    if (!callsign) {
      return res.status(400).json({ error: 'callsign is required' });
    }

    const club = db.prepare('SELECT * FROM clubs WHERE id = ?').get(req.params.clubId);
    if (!club) return res.status(404).json({ error: 'Club not found' });

    try {
      const info = db.prepare(
        'INSERT INTO operators (callsign, club_id, contest_id) VALUES (?, ?, ?)'
      ).run(callsign, req.params.clubId, club.contest_id);
      const operator = db.prepare('SELECT * FROM operators WHERE id = ?').get(info.lastInsertRowid);
      res.status(201).json(operator);
    } catch (err) {
      res.status(500).json({ error: err.message });
    }
  });

  // Remove operator
  router.delete('/api/operators/:id', (req, res) => {
    try {
      const info = db.prepare('DELETE FROM operators WHERE id = ?').run(req.params.id);
      if (info.changes === 0) return res.status(404).json({ error: 'Operator not found' });
      res.json({ ok: true });
    } catch (err) {
      res.status(500).json({ error: err.message });
    }
  });

  return router;
}
