import express from 'express';
import cors from 'cors';
import { createServer } from 'http';
import { WebSocketServer } from 'ws';
import { createSocket } from 'dgram';
import path from 'path';
import { fileURLToPath } from 'url';

import { initDb } from './db/schema.js';
import { DB_PATH, PORT, UDP_PORT } from './config.js';
import { parseAdif } from './services/adifParser.js';
import { WsBroadcast } from './ws/broadcast.js';

import contestRoutes from './routes/contests.js';
import clubRoutes from './routes/clubs.js';
import qsoRoutes from './routes/qsos.js';
import statsRoutes from './routes/stats.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Initialize database
const db = initDb(DB_PATH);

// Express app
const app = express();
app.use(cors());
app.use(express.json());

// Mount routes
app.use(contestRoutes(db));
app.use(clubRoutes(db));
app.use(qsoRoutes(db));
app.use(statsRoutes(db));

// Serve static files in production
if (process.env.NODE_ENV === 'production') {
  const distPath = path.resolve(__dirname, '..', 'dist');
  app.use(express.static(distPath));
  app.get('*', (req, res) => {
    res.sendFile(path.join(distPath, 'index.html'));
  });
}

// HTTP server
const server = createServer(app);

// WebSocket server
const wsBroadcast = new WsBroadcast(db);
const wss = new WebSocketServer({ noServer: true });

server.on('upgrade', (request, socket, head) => {
  wss.handleUpgrade(request, socket, head, (ws) => {
    wsBroadcast.handleConnection(ws);
  });
});

// UDP listener for ADIF messages
const udp = createSocket('udp4');

udp.on('message', (msg) => {
  if (msg.length > 65536) return; // Ignore oversized messages
  try {
    const raw = msg.toString('utf8');
    const parsed = parseAdif(raw);

    if (!parsed.call || !parsed.station_callsign) {
      return; // Skip incomplete records
    }

    // Find the active contest
    const contest = db.prepare(
      "SELECT id FROM contests WHERE status = 'active' LIMIT 1"
    ).get();

    if (!contest) return;

    const info = db.prepare(`
      INSERT INTO qsos (
        contest_id, station_callsign, call, band, mode, frequency,
        rst_sent, rst_rcvd, gridsquare, my_gridsquare,
        qso_date, time_on, time_off, points, is_multiplier, raw_adif
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).run(
      contest.id,
      parsed.station_callsign, parsed.call,
      parsed.band, parsed.mode, parsed.frequency,
      parsed.rst_sent, parsed.rst_rcvd,
      parsed.gridsquare, parsed.my_gridsquare,
      parsed.qso_date, parsed.time_on, parsed.time_off,
      1, 0, raw
    );

    const qso = db.prepare('SELECT * FROM qsos WHERE id = ?').get(info.lastInsertRowid);

    // Broadcast to WebSocket clients
    wsBroadcast.broadcastQso(qso);

    // Also send updated scoreboard
    const scoreboard = db.prepare(`
      SELECT
        station_callsign,
        COUNT(*) AS qso_count,
        SUM(points) AS total_points,
        SUM(is_multiplier) AS multipliers,
        SUM(points) * MAX(1, SUM(is_multiplier)) AS score
      FROM qsos
      WHERE contest_id = ?
      GROUP BY station_callsign
      ORDER BY score DESC
    `).all(contest.id);
    wsBroadcast.broadcastScoreboard(scoreboard);
  } catch (err) {
    console.error('UDP parse error:', err.message);
  }
});

udp.on('error', (err) => {
  console.error('UDP error:', err.message);
});

udp.bind(UDP_PORT, () => {
  console.log(`UDP listening on port ${UDP_PORT}`);
});

// Start HTTP server
server.listen(PORT, () => {
  console.log(`RadioRumble server running on port ${PORT}`);
});
