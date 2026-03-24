import { initDb } from '../server/db/schema.js';
import {
  createContest,
  createClub,
  addOperator,
  insertQso,
  getScoreboard,
  getStats,
} from '../server/db/queries.js';
import { DB_PATH } from '../server/config.js';

// ── Seed data ──────────────────────────────────────────────

const CLUBS = [
  {
    name: 'K-State Wildcats',
    callsign: 'W0QQQ',
    operators: ['AB0ZW', 'KE0VUM', 'KD2FMW', 'K0KSU'],
  },
  {
    name: 'KU Jayhawks',
    callsign: 'W0KU',
    operators: ['N0CALL', 'W1AW', 'KC0JHK'],
  },
  {
    name: 'Mizzou Tigers',
    callsign: 'W0MU',
    operators: ['VA3OFF', 'KG7YDB', 'W0MZU', 'N5MO'],
  },
  {
    name: 'Iowa State Cyclones',
    callsign: 'W0ISU',
    operators: ['K0ISU', 'WB0CMC', 'KD0SVI'],
  },
];

const BANDS = ['20m', '40m', '15m', '10m', '80m'];
const MODES = ['FT8', 'FT4', 'CW', 'SSB'];
const FREQUENCIES = {
  '20m': [14074, 14250],
  '40m': [7074, 7200],
  '15m': [21074, 21300],
  '10m': [28074, 28400],
  '80m': [3573, 3800],
};

const GRIDS = [
  'EM28', 'EM29', 'EM38', 'EM48', 'EN31', 'EN32', 'EN41', 'EN42',
  'FN31', 'FN42', 'FN20', 'FN03', 'DM79', 'DM65', 'CM97', 'CM88',
  'DN70', 'DN31', 'EL29', 'EL96', 'IO91', 'JO31', 'JN48', 'JO62',
  'PM95', 'QM06', 'PM74', 'PM85',
];

const DX_CALLS = [
  'JA1XYZ', 'DL3ABC', 'G4DEF', 'VK2GHI', 'ZL1JKL', 'EA5MNO',
  'F6PQR', 'ON4STU', 'PA3VWX', 'SM5YZA', 'OH2BCD', 'LU8EFG',
  'PY2HIJ', 'UA3KLM', 'HS0NOP', 'VR2QRS', 'A61TUV', 'ZS6WXY',
  'VE3ZAB', 'XE1CDE', '9A2FGH', 'OZ1IJK', 'SP9LMN', 'HB9OPQ',
];

// ── Helpers ────────────────────────────────────────────────

function pick(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}

function randInt(min, max) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

function padTwo(n) {
  return String(n).padStart(2, '0');
}

// ── Main ───────────────────────────────────────────────────

console.log(`Seeding database at ${DB_PATH} ...`);

const db = initDb(DB_PATH);

const now = new Date();
const twoHoursAgo = new Date(now.getTime() - 2 * 60 * 60 * 1000);
const fourHoursFromNow = new Date(now.getTime() + 4 * 60 * 60 * 1000);

// Create contest
const contest = createContest(db, {
  name: 'K-State Spring QSO Party 2026',
  description: 'Annual spring amateur radio contest hosted by K-State',
  startTime: now.toISOString(),
  endTime: fourHoursFromNow.toISOString(),
});

// Set contest to active
db.prepare("UPDATE contests SET status = 'active' WHERE id = ?").run(contest.id);

console.log(`  Contest: ${contest.name} (id=${contest.id})`);

// Create clubs and operators
const allOperators = []; // { callsign, clubId, contestId }

for (const clubDef of CLUBS) {
  const club = createClub(db, {
    name: clubDef.name,
    callsign: clubDef.callsign,
    contestId: contest.id,
  });
  console.log(`  Club: ${club.name} (${club.callsign})`);

  for (const opCall of clubDef.operators) {
    const op = addOperator(db, {
      callsign: opCall,
      clubId: club.id,
      contestId: contest.id,
    });
    allOperators.push(op);
    console.log(`    Operator: ${opCall}`);
  }
}

// Generate 200 mock QSOs
const QSO_COUNT = 200;
console.log(`\n  Generating ${QSO_COUNT} mock QSOs ...`);

const insertMany = db.transaction(() => {
  for (let i = 0; i < QSO_COUNT; i++) {
    const op = pick(allOperators);
    const band = pick(BANDS);
    const mode = pick(MODES);
    const freqs = FREQUENCIES[band];
    const frequency = freqs[mode === 'SSB' ? 1 : 0] || freqs[0];

    // Timestamp spread over the last 2 hours
    const offsetMs = Math.random() * 2 * 60 * 60 * 1000;
    const ts = new Date(twoHoursAgo.getTime() + offsetMs);
    const qsoDate = `${ts.getUTCFullYear()}${padTwo(ts.getUTCMonth() + 1)}${padTwo(ts.getUTCDate())}`;
    const timeOn = `${padTwo(ts.getUTCHours())}${padTwo(ts.getUTCMinutes())}${padTwo(ts.getUTCSeconds())}`;

    // Signal report
    const snr = randInt(-10, 5);
    const rstSent = snr >= 0 ? `+${padTwo(snr)}` : `${snr}`;
    const rstRcvd = (() => {
      const r = randInt(-10, 5);
      return r >= 0 ? `+${padTwo(r)}` : `${r}`;
    })();

    insertQso(db, {
      contestId: contest.id,
      stationCallsign: op.callsign,
      call: pick(DX_CALLS),
      band,
      mode,
      frequency,
      rstSent,
      rstRcvd,
      gridsquare: pick(GRIDS),
      myGridsquare: 'EM28',
      qsoDate,
      timeOn,
      timeOff: timeOn,
      isMultiplier: Math.random() < 0.15 ? 1 : 0,
      points: 1,
    });
  }
});

insertMany();

// Print summary
const stats = getStats(db, contest.id);
const scoreboard = getScoreboard(db, contest.id);

console.log('\n── Seed Summary ──────────────────────────────');
console.log(`  Contest:    ${contest.name}`);
console.log(`  Clubs:      ${CLUBS.length}`);
console.log(`  Operators:  ${allOperators.length}`);
console.log(`  QSOs:       ${stats.totalQsos}`);
console.log(`  Bands:      ${stats.bandDistribution.map(b => `${b.band}(${b.count})`).join(', ')}`);
console.log(`  Modes:      ${stats.modeDistribution.map(m => `${m.mode}(${m.count})`).join(', ')}`);
console.log('\n  Scoreboard:');
for (const row of scoreboard) {
  console.log(`    ${row.station_callsign.padEnd(10)} ${row.qso_count} QSOs  ${row.total_points} pts`);
}
console.log('──────────────────────────────────────────────\n');

db.close();
console.log('Database seeded and closed.');
