import React from 'react';
import { ClubTotal } from '../../types/ws';

/* ── props ───────────────────────────────────────────────── */
interface ClubTotalsProps {
  clubTotals: ClubTotal[];
}

/* ═══════════════════════════════════════════════════════════
   ClubTotals — "TEAM STANDINGS" aggregate scores
   ═══════════════════════════════════════════════════════════ */
const ClubTotals: React.FC<ClubTotalsProps> = ({ clubTotals }) => {
  if (clubTotals.length === 0) return null;

  /* sort by points descending */
  const sorted = [...clubTotals].sort((a, b) => b.totalPoints - a.totalPoints);

  return (
    <div
      style={{
        background: 'var(--bg-card)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-md)',
        padding: 20,
        marginTop: 20,
      }}
    >
      <h3
        style={{
          margin: '0 0 14px',
          fontSize: 14,
          fontWeight: 700,
          letterSpacing: '0.08em',
          textTransform: 'uppercase',
          color: 'var(--accent)',
        }}
      >
        Team Standings
      </h3>

      <table>
        <thead>
          <tr>
            <th style={{ width: 42, textAlign: 'center' }}>#</th>
            <th>Club</th>
            <th style={{ textAlign: 'right' }}>QSOs</th>
            <th style={{ textAlign: 'right' }}>Points</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((club, idx) => {
            const isLeader = idx === 0;
            return (
              <tr
                key={club.clubName}
                style={{
                  borderLeft: isLeader
                    ? '3px solid var(--accent)'
                    : '3px solid transparent',
                  background: isLeader
                    ? 'linear-gradient(90deg, rgba(244,197,92,0.08) 0%, transparent 60%)'
                    : undefined,
                }}
              >
                {/* Rank */}
                <td
                  style={{
                    textAlign: 'center',
                    fontWeight: 700,
                    fontSize: isLeader ? 16 : 14,
                    color: isLeader ? 'var(--accent)' : 'var(--text-secondary)',
                  }}
                >
                  {isLeader ? (
                    <span
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 2,
                      }}
                    >
                      <svg
                        width="12"
                        height="12"
                        viewBox="0 0 24 24"
                        fill="var(--accent)"
                        style={{ marginRight: 2 }}
                      >
                        <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z" />
                      </svg>
                      {idx + 1}
                    </span>
                  ) : (
                    idx + 1
                  )}
                </td>

                {/* Club name */}
                <td
                  style={{
                    fontWeight: 700,
                    fontSize: 14,
                    color: isLeader ? 'var(--accent)' : 'var(--text-primary)',
                    textShadow: isLeader
                      ? '0 0 12px rgba(244,197,92,0.25)'
                      : 'none',
                  }}
                >
                  {club.clubName}
                </td>

                {/* QSOs */}
                <td
                  style={{
                    textAlign: 'right',
                    fontFamily: "'JetBrains Mono', monospace",
                    fontWeight: 600,
                    fontSize: 14,
                    color: 'var(--text-primary)',
                  }}
                >
                  {club.totalQsos.toLocaleString()}
                </td>

                {/* Points */}
                <td
                  style={{
                    textAlign: 'right',
                    fontFamily: "'JetBrains Mono', monospace",
                    fontWeight: 700,
                    fontSize: 14,
                    color: isLeader ? 'var(--accent)' : 'var(--text-primary)',
                  }}
                >
                  {club.totalPoints.toLocaleString()}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};

export default ClubTotals;
