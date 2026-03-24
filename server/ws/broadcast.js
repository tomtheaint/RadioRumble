export class WsBroadcast {
  constructor(db) {
    this.db = db;
    this.clients = new Set();
  }

  /**
   * Handle a new WebSocket connection.
   * Adds the client and sends the current scoreboard snapshot.
   */
  handleConnection(ws) {
    this.clients.add(ws);

    ws.on('close', () => this.removeClient(ws));
    ws.on('error', () => this.removeClient(ws));

    // Send initial scoreboard snapshot
    try {
      const scoreboard = this._buildScoreboard();
      ws.send(JSON.stringify({ type: 'scoreboard', data: scoreboard }));
    } catch {
      // Client may have disconnected immediately
    }
  }

  /**
   * Send a JSON message to all connected clients.
   */
  broadcast(message) {
    const payload = typeof message === 'string' ? message : JSON.stringify(message);
    const deadClients = [];
    for (const client of this.clients) {
      try {
        if (client.readyState === 1) { // WebSocket.OPEN
          client.send(payload);
        }
      } catch {
        deadClients.push(client);
      }
    }
    for (const client of deadClients) {
      this.removeClient(client);
    }
  }

  /**
   * Broadcast a new QSO to all clients.
   */
  broadcastQso(qso) {
    this.broadcast({ type: 'qso', data: qso });
  }

  /**
   * Broadcast a full scoreboard update.
   */
  broadcastScoreboard(data) {
    this.broadcast({ type: 'scoreboard', data });
  }

  /**
   * Remove a client from the tracked set.
   */
  removeClient(ws) {
    this.clients.delete(ws);
  }

  /**
   * Build the current scoreboard from the active contest.
   * Returns the same format as the REST /scoreboard endpoint.
   */
  _buildScoreboard() {
    const contest = this.db.prepare(
      "SELECT * FROM contests WHERE status = 'active' LIMIT 1"
    ).get();

    if (!contest) return { stations: [], clubTotals: [], contestStatus: 'pending', elapsed: 0, remaining: null };

    const contestId = contest.id;

    const stations = this.db.prepare(`
      SELECT station_callsign, COUNT(*) AS qso_count, COALESCE(SUM(points), 0) AS total_points
      FROM qsos WHERE contest_id = ? GROUP BY station_callsign ORDER BY total_points DESC
    `).all(contestId);

    const bandRows = this.db.prepare(`
      SELECT station_callsign, band, COUNT(*) AS count
      FROM qsos WHERE contest_id = ? GROUP BY station_callsign, band
    `).all(contestId);

    const modeRows = this.db.prepare(`
      SELECT station_callsign, mode, COUNT(*) AS count
      FROM qsos WHERE contest_id = ? GROUP BY station_callsign, mode
    `).all(contestId);

    const operators = this.db.prepare(`
      SELECT o.callsign, c.name AS club_name
      FROM operators o JOIN clubs c ON o.club_id = c.id
      WHERE o.contest_id = ?
    `).all(contestId);
    const opClubMap = {};
    for (const op of operators) opClubMap[op.callsign] = op.club_name;

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

    const rateRows = this.db.prepare(`
      SELECT station_callsign, COUNT(*) AS rate
      FROM qsos
      WHERE contest_id = ? AND created_at >= datetime('now', '-1 hour')
      GROUP BY station_callsign
    `).all(contestId);
    const rateMap = {};
    for (const r of rateRows) rateMap[r.station_callsign] = r.rate;

    const result = stations.map(s => ({
      callsign: s.station_callsign,
      clubName: opClubMap[s.station_callsign] || null,
      totalQsos: s.qso_count,
      totalPoints: s.total_points,
      bands: bandMap[s.station_callsign] || {},
      modes: modeMap[s.station_callsign] || {},
      rate: rateMap[s.station_callsign] || 0,
    }));

    const clubTotals = this.db.prepare(`
      SELECT c.name AS club_name, COUNT(q.id) AS total_qsos, COALESCE(SUM(q.points), 0) AS total_points
      FROM clubs c
      LEFT JOIN operators o ON o.club_id = c.id AND o.contest_id = c.contest_id
      LEFT JOIN qsos q ON q.station_callsign = o.callsign AND q.contest_id = o.contest_id
      WHERE c.contest_id = ?
      GROUP BY c.name ORDER BY total_points DESC
    `).all(contestId);

    return {
      stations: result,
      clubTotals: clubTotals.map(c => ({
        clubName: c.club_name,
        totalQsos: c.total_qsos,
        totalPoints: c.total_points,
      })),
      contestStatus: contest.status,
      elapsed: contest.start_time ? Math.floor((Date.now() - new Date(contest.start_time).getTime()) / 1000) : 0,
      remaining: contest.end_time ? Math.max(0, Math.floor((new Date(contest.end_time).getTime() - Date.now()) / 1000)) : null,
    };
  }
}
