// --------------- Contests ---------------

export function createContest(db, { name, description, startTime, endTime, rules }) {
  const stmt = db.prepare(`
    INSERT INTO contests (name, description, start_time, end_time, rules)
    VALUES (?, ?, ?, ?, ?)
  `);
  const info = stmt.run(name, description || null, startTime, endTime, rules ? JSON.stringify(rules) : null);
  return getContest(db, info.lastInsertRowid);
}

export function getContests(db) {
  return db.prepare('SELECT * FROM contests ORDER BY start_time DESC').all();
}

export function getContest(db, id) {
  return db.prepare('SELECT * FROM contests WHERE id = ?').get(id);
}

export function updateContest(db, id, fields) {
  const allowed = ['name', 'description', 'start_time', 'end_time', 'status', 'rules'];
  const cols = [];
  const vals = [];

  for (const [key, value] of Object.entries(fields)) {
    const col = key.replace(/([A-Z])/g, '_$1').toLowerCase(); // camelCase -> snake_case
    if (allowed.includes(col)) {
      cols.push(`${col} = ?`);
      vals.push(col === 'rules' && typeof value === 'object' ? JSON.stringify(value) : value);
    }
  }

  if (cols.length === 0) return getContest(db, id);

  vals.push(id);
  db.prepare(`UPDATE contests SET ${cols.join(', ')} WHERE id = ?`).run(...vals);
  return getContest(db, id);
}

export function deleteContest(db, id) {
  return db.prepare('DELETE FROM contests WHERE id = ?').run(id);
}

// --------------- Clubs ---------------

export function createClub(db, { name, callsign, contestId }) {
  const info = db.prepare(`
    INSERT INTO clubs (name, callsign, contest_id) VALUES (?, ?, ?)
  `).run(name, callsign, contestId);
  return db.prepare('SELECT * FROM clubs WHERE id = ?').get(info.lastInsertRowid);
}

export function getClubs(db, contestId) {
  return db.prepare('SELECT * FROM clubs WHERE contest_id = ? ORDER BY name').all(contestId);
}

export function updateClub(db, id, fields) {
  const allowed = ['name', 'callsign'];
  const cols = [];
  const vals = [];

  for (const [key, value] of Object.entries(fields)) {
    if (allowed.includes(key)) {
      cols.push(`${key} = ?`);
      vals.push(value);
    }
  }

  if (cols.length === 0) return db.prepare('SELECT * FROM clubs WHERE id = ?').get(id);

  vals.push(id);
  db.prepare(`UPDATE clubs SET ${cols.join(', ')} WHERE id = ?`).run(...vals);
  return db.prepare('SELECT * FROM clubs WHERE id = ?').get(id);
}

export function deleteClub(db, id) {
  return db.prepare('DELETE FROM clubs WHERE id = ?').run(id);
}

// --------------- Operators ---------------

export function addOperator(db, { callsign, clubId, contestId }) {
  const info = db.prepare(`
    INSERT INTO operators (callsign, club_id, contest_id) VALUES (?, ?, ?)
  `).run(callsign, clubId, contestId);
  return db.prepare('SELECT * FROM operators WHERE id = ?').get(info.lastInsertRowid);
}

export function getOperators(db, contestId) {
  return db.prepare('SELECT * FROM operators WHERE contest_id = ? ORDER BY callsign').all(contestId);
}

export function removeOperator(db, id) {
  return db.prepare('DELETE FROM operators WHERE id = ?').run(id);
}

// --------------- QSOs ---------------

export function insertQso(db, qsoData) {
  const stmt = db.prepare(`
    INSERT INTO qsos (
      contest_id, station_callsign, call, band, mode, frequency,
      rst_sent, rst_rcvd, gridsquare, my_gridsquare,
      qso_date, time_on, time_off, is_multiplier, points, raw_adif
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `);

  const info = stmt.run(
    qsoData.contestId,
    qsoData.stationCallsign,
    qsoData.call,
    qsoData.band || null,
    qsoData.mode || null,
    qsoData.frequency || null,
    qsoData.rstSent || null,
    qsoData.rstRcvd || null,
    qsoData.gridsquare || null,
    qsoData.myGridsquare || null,
    qsoData.qsoDate || null,
    qsoData.timeOn || null,
    qsoData.timeOff || null,
    qsoData.isMultiplier || 0,
    qsoData.points || 1,
    qsoData.rawAdif || null
  );

  return db.prepare('SELECT * FROM qsos WHERE id = ?').get(info.lastInsertRowid);
}

export function getQsos(db, contestId, { limit = 100, offset = 0, band, mode, station } = {}) {
  let sql = 'SELECT * FROM qsos WHERE contest_id = ?';
  const params = [contestId];

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
  params.push(limit, offset);

  return db.prepare(sql).all(...params);
}

export function getRecentQsos(db, contestId, limit = 50) {
  return db.prepare(`
    SELECT * FROM qsos
    WHERE contest_id = ?
    ORDER BY created_at DESC
    LIMIT ?
  `).all(contestId, limit);
}

// --------------- Aggregates ---------------

export function getScoreboard(db, contestId) {
  return db.prepare(`
    SELECT
      station_callsign,
      COUNT(*) AS qso_count,
      SUM(points) AS total_points,
      COUNT(DISTINCT band) AS bands_worked,
      COUNT(DISTINCT mode) AS modes_worked,
      SUM(is_multiplier) AS multipliers,
      json_group_array(DISTINCT band) AS bands,
      json_group_array(DISTINCT mode) AS modes
    FROM qsos
    WHERE contest_id = ?
    GROUP BY station_callsign
    ORDER BY total_points DESC
  `).all(contestId).map(row => ({
    ...row,
    bands: row.bands ? JSON.parse(row.bands).filter(Boolean) : [],
    modes: row.modes ? JSON.parse(row.modes).filter(Boolean) : [],
  }));
}

export function getStats(db, contestId) {
  const bandDist = db.prepare(`
    SELECT band, COUNT(*) AS count
    FROM qsos
    WHERE contest_id = ? AND band IS NOT NULL
    GROUP BY band
    ORDER BY count DESC
  `).all(contestId);

  const modeDist = db.prepare(`
    SELECT mode, COUNT(*) AS count
    FROM qsos
    WHERE contest_id = ? AND mode IS NOT NULL
    GROUP BY mode
    ORDER BY count DESC
  `).all(contestId);

  const total = db.prepare('SELECT COUNT(*) AS count FROM qsos WHERE contest_id = ?').get(contestId);

  return {
    totalQsos: total.count,
    bandDistribution: bandDist,
    modeDistribution: modeDist,
  };
}

export function getRateData(db, contestId) {
  return db.prepare(`
    SELECT
      qso_date,
      substr(time_on, 1, 2) AS hour,
      COUNT(*) AS count
    FROM qsos
    WHERE contest_id = ? AND qso_date IS NOT NULL AND time_on IS NOT NULL
    GROUP BY qso_date, substr(time_on, 1, 2)
    ORDER BY qso_date, hour
  `).all(contestId);
}

export function getMapData(db, contestId) {
  return db.prepare(`
    SELECT
      id, call, gridsquare, my_gridsquare, band, mode, frequency,
      station_callsign, qso_date, time_on, points
    FROM qsos
    WHERE contest_id = ? AND gridsquare IS NOT NULL AND gridsquare != ''
    ORDER BY created_at DESC
  `).all(contestId);
}
