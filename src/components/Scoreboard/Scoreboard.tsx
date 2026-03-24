import React, { useEffect } from 'react';
import { useScoreboardStore } from '../../stores/useScoreboardStore';
import { useContestStore } from '../../stores/useContestStore';
import { useQsoStore } from '../../stores/useQsoStore';
import ScoreRow from './ScoreRow';
import QsoFeed from '../QsoFeed/QsoFeed';

const STATUS_COLORS: Record<string, { bg: string; text: string; label: string }> = {
  active: { bg: '#00c853', text: '#fff', label: 'LIVE' },
  pending: { bg: '#F4C55C', text: '#1a1a2e', label: 'PENDING' },
  completed: { bg: '#ff5252', text: '#fff', label: 'ENDED' },
};

function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

const Scoreboard: React.FC = () => {
  const stations = useScoreboardStore((s) => s.stations);
  const clubTotals = useScoreboardStore((s) => s.clubTotals);
  const updateFromSnapshot = useScoreboardStore((s) => s.updateFromSnapshot);
  const contest = useContestStore((s) => s.activeContest);
  const status = useContestStore((s) => s.status);
  const elapsed = useContestStore((s) => s.elapsed);
  const remaining = useContestStore((s) => s.remaining);
  const setQsos = useQsoStore((s) => s.setQsos);

  // Fetch initial data from REST API
  useEffect(() => {
    const contestId = contest?.id || 1;
    fetch(`/api/contests/${contestId}/scoreboard`)
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data?.stations) updateFromSnapshot(data);
      })
      .catch(() => {});
    fetch(`/api/contests/${contestId}/qsos/recent`)
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (Array.isArray(data)) setQsos(data.map((q: any) => ({
          id: q.id, contestId: q.contest_id, stationCallsign: q.station_callsign,
          call: q.call, band: q.band, mode: q.mode, gridsquare: q.gridsquare,
          myGridsquare: q.my_gridsquare, timeOn: q.time_on, qsoDate: q.qso_date,
          isMultiplier: !!q.is_multiplier, points: q.points, createdAt: q.created_at,
        })));
      })
      .catch(() => {});
  }, [contest?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const sorted = [...stations].sort((a, b) => b.totalPoints - a.totalPoints);
  const sortedClubs = [...clubTotals].sort((a, b) => b.totalPoints - a.totalPoints);
  const statusInfo = STATUS_COLORS[status] || STATUS_COLORS.pending;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Contest Header */}
      <div
        className="scoreboard-header-mobile"
        style={{
          background: 'var(--bg-card)',
          border: '1px solid var(--border)',
          borderRadius: 12,
          padding: '20px 28px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 16,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <h1
            style={{
              margin: 0,
              fontSize: 22,
              fontWeight: 800,
              color: 'var(--text-primary)',
              letterSpacing: 0.5,
            }}
          >
            {contest?.name || 'Radio Rumble'}
          </h1>
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              padding: '3px 12px',
              borderRadius: 9999,
              fontSize: 11,
              fontWeight: 800,
              letterSpacing: 1.2,
              textTransform: 'uppercase',
              background: statusInfo.bg,
              color: statusInfo.text,
              boxShadow: status === 'active' ? `0 0 12px ${statusInfo.bg}66` : 'none',
            }}
          >
            {status === 'active' && (
              <span
                style={{
                  width: 7,
                  height: 7,
                  borderRadius: '50%',
                  background: '#fff',
                  animation: 'pulse-dot 1.5s ease-in-out infinite',
                }}
              />
            )}
            {statusInfo.label}
          </span>
        </div>

        <div style={{ display: 'flex', gap: 24, alignItems: 'center' }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: 1 }}>
              Elapsed
            </div>
            <div
              style={{
                fontSize: 20,
                fontWeight: 700,
                fontFamily: "'JetBrains Mono', monospace",
                color: 'var(--text-primary)',
              }}
            >
              {formatDuration(elapsed)}
            </div>
          </div>
          {remaining !== null && (
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: 1 }}>
                Remaining
              </div>
              <div
                style={{
                  fontSize: 20,
                  fontWeight: 700,
                  fontFamily: "'JetBrains Mono', monospace",
                  color: remaining < 600 ? '#ff5252' : 'var(--accent)',
                }}
              >
                {formatDuration(remaining)}
              </div>
            </div>
          )}
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: 1 }}>
              Stations
            </div>
            <div
              style={{
                fontSize: 20,
                fontWeight: 700,
                fontFamily: "'JetBrains Mono', monospace",
                color: 'var(--text-primary)',
              }}
            >
              {stations.length}
            </div>
          </div>
        </div>
      </div>

      {/* Main Scoreboard Table */}
      <div
        style={{
          background: 'var(--bg-card)',
          border: '1px solid var(--border)',
          borderRadius: 12,
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            padding: '14px 20px',
            borderBottom: '1px solid var(--border)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <h2
            style={{
              margin: 0,
              fontSize: 14,
              fontWeight: 700,
              color: 'var(--text-secondary)',
              textTransform: 'uppercase',
              letterSpacing: 1.5,
            }}
          >
            Station Leaderboard
          </h2>
          <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
            {sorted.length} station{sorted.length !== 1 ? 's' : ''}
          </span>
        </div>

        {sorted.length === 0 ? (
          <div
            style={{
              padding: '60px 20px',
              textAlign: 'center',
            }}
          >
            <div
              style={{
                fontSize: 32,
                marginBottom: 12,
                opacity: 0.3,
              }}
            >
              <svg width="48" height="48" viewBox="0 0 24 24" fill="var(--text-secondary)" style={{ opacity: 0.4 }}>
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" />
              </svg>
            </div>
            <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-secondary)' }}>
              Waiting for QSOs...
            </div>
            <div style={{ fontSize: 13, color: 'var(--text-secondary)', opacity: 0.6, marginTop: 4 }}>
              Scores will appear as contacts are logged
            </div>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table
              style={{
                width: '100%',
                borderCollapse: 'collapse',
                fontSize: 14,
              }}
            >
              <thead>
                <tr
                  style={{
                    borderBottom: '1px solid var(--border)',
                    background: 'rgba(81,40,136,0.15)',
                  }}
                >
                  {['#', 'Callsign', 'Club', 'QSOs', 'Points', 'Bands', 'Rate'].map((h) => (
                    <th
                      key={h}
                      style={{
                        padding: '10px 12px',
                        textAlign: h === 'QSOs' || h === 'Points' || h === 'Rate' ? 'right' : 'left',
                        fontSize: 10,
                        fontWeight: 700,
                        color: 'var(--text-secondary)',
                        textTransform: 'uppercase',
                        letterSpacing: 1.2,
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sorted.map((station, i) => (
                  <ScoreRow
                    key={station.callsign}
                    rank={i + 1}
                    station={station}
                    isLeader={i === 0}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Club Totals */}
      {sortedClubs.length > 0 && (
        <div
          style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--border)',
            borderRadius: 12,
            overflow: 'hidden',
          }}
        >
          <div
            style={{
              padding: '14px 20px',
              borderBottom: '1px solid var(--border)',
            }}
          >
            <h2
              style={{
                margin: 0,
                fontSize: 14,
                fontWeight: 700,
                color: 'var(--text-secondary)',
                textTransform: 'uppercase',
                letterSpacing: 1.5,
              }}
            >
              Club Standings
            </h2>
          </div>

          <div style={{ overflowX: 'auto' }}>
            <table
              style={{
                width: '100%',
                borderCollapse: 'collapse',
                fontSize: 14,
              }}
            >
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)', background: 'rgba(81,40,136,0.15)' }}>
                  {['#', 'Club', 'QSOs', 'Points'].map((h) => (
                    <th
                      key={h}
                      style={{
                        padding: '10px 12px',
                        textAlign: h === 'QSOs' || h === 'Points' ? 'right' : 'left',
                        fontSize: 10,
                        fontWeight: 700,
                        color: 'var(--text-secondary)',
                        textTransform: 'uppercase',
                        letterSpacing: 1.2,
                      }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sortedClubs.map((club, i) => (
                  <tr
                    key={club.clubName}
                    style={{
                      borderBottom: '1px solid var(--border)',
                      borderLeft: i === 0 ? '3px solid var(--accent)' : '3px solid transparent',
                      background: i === 0
                        ? 'linear-gradient(90deg, rgba(244,197,92,0.08) 0%, transparent 60%)'
                        : undefined,
                    }}
                  >
                    <td
                      style={{
                        padding: '10px 12px',
                        textAlign: 'center',
                        fontWeight: 700,
                        color: i === 0 ? 'var(--accent)' : 'var(--text-secondary)',
                        width: 48,
                      }}
                    >
                      {i + 1}
                    </td>
                    <td
                      style={{
                        padding: '10px 12px',
                        fontWeight: 600,
                        color: i === 0 ? 'var(--accent)' : 'var(--text-primary)',
                      }}
                    >
                      {club.clubName}
                    </td>
                    <td
                      style={{
                        padding: '10px 12px',
                        textAlign: 'right',
                        fontWeight: 600,
                        fontFamily: "'JetBrains Mono', monospace",
                        color: 'var(--text-primary)',
                      }}
                    >
                      {club.totalQsos.toLocaleString()}
                    </td>
                    <td
                      style={{
                        padding: '10px 12px',
                        textAlign: 'right',
                        fontWeight: 700,
                        fontFamily: "'JetBrains Mono', monospace",
                        color: i === 0 ? 'var(--accent)' : 'var(--text-primary)',
                      }}
                    >
                      {club.totalPoints.toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* QSO Live Feed */}
      <QsoFeed />

      <style>{`
        @keyframes pulse-dot {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.3; }
        }
        @media (max-width: 768px) {
          .scoreboard-header-mobile h1 {
            font-size: 16px !important;
          }
          .scoreboard-header-mobile > div:last-child {
            gap: 12px !important;
          }
          .scoreboard-header-mobile > div:last-child > div > div:first-child {
            font-size: 9px !important;
          }
          .scoreboard-header-mobile > div:last-child > div > div:last-child {
            font-size: 16px !important;
          }
        }
      `}</style>
    </div>
  );
};

export default Scoreboard;
