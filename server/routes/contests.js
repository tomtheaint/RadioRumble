import { Router } from 'express';

function mapContest(r) {
  return {
    id: r.id, name: r.name, description: r.description,
    startTime: r.start_time, endTime: r.end_time,
    status: r.status, rules: r.rules, createdAt: r.created_at
  };
}

export default function contestRoutes(db) {
  const router = Router();

  // List all contests
  router.get('/api/contests', (req, res) => {
    try {
      const rows = db.prepare('SELECT * FROM contests ORDER BY created_at DESC').all();
      const mapped = rows.map(mapContest);
      res.json(mapped);
    } catch (err) {
      res.status(500).json({ error: err.message });
    }
  });

  // Create contest
  router.post('/api/contests', (req, res) => {
    const { name, description, startTime, endTime, rules } = req.body;
    if (!name || !startTime || !endTime) {
      return res.status(400).json({ error: 'name, startTime, and endTime are required' });
    }
    try {
      const info = db.prepare(
        'INSERT INTO contests (name, description, start_time, end_time, rules) VALUES (?, ?, ?, ?, ?)'
      ).run(name, description || null, startTime, endTime, rules || null);
      const contest = db.prepare('SELECT * FROM contests WHERE id = ?').get(info.lastInsertRowid);
      res.status(201).json(mapContest(contest));
    } catch (err) {
      res.status(500).json({ error: err.message });
    }
  });

  // Get one contest
  router.get('/api/contests/:id', (req, res) => {
    try {
      const contest = db.prepare('SELECT * FROM contests WHERE id = ?').get(req.params.id);
      if (!contest) return res.status(404).json({ error: 'Contest not found' });
      res.json(mapContest(contest));
    } catch (err) {
      res.status(500).json({ error: err.message });
    }
  });

  // Update contest
  router.patch('/api/contests/:id', (req, res) => {
    const contest = db.prepare('SELECT * FROM contests WHERE id = ?').get(req.params.id);
    if (!contest) return res.status(404).json({ error: 'Contest not found' });

    const fields = [];
    const values = [];

    for (const [key, col] of [
      ['name', 'name'],
      ['description', 'description'],
      ['startTime', 'start_time'],
      ['endTime', 'end_time'],
      ['status', 'status'],
      ['rules', 'rules'],
    ]) {
      if (req.body[key] !== undefined) {
        fields.push(`${col} = ?`);
        values.push(req.body[key]);
      }
    }

    if (fields.length === 0) {
      return res.status(400).json({ error: 'No valid fields to update' });
    }

    try {
      values.push(req.params.id);
      db.prepare(`UPDATE contests SET ${fields.join(', ')} WHERE id = ?`).run(...values);
      const updated = db.prepare('SELECT * FROM contests WHERE id = ?').get(req.params.id);
      res.json(mapContest(updated));
    } catch (err) {
      res.status(500).json({ error: err.message });
    }
  });

  // Delete contest
  router.delete('/api/contests/:id', (req, res) => {
    try {
      const info = db.prepare('DELETE FROM contests WHERE id = ?').run(req.params.id);
      if (info.changes === 0) return res.status(404).json({ error: 'Contest not found' });
      res.json({ ok: true });
    } catch (err) {
      res.status(500).json({ error: err.message });
    }
  });

  return router;
}
