import React from 'react';
import { StationScore } from '../../types/ws';
import BandBreakdown from './BandBreakdown';
import RateGraph from './RateGraph';

interface ScoreRowProps {
  rank: number;
  station: StationScore;
  isLeader: boolean;
}

const ScoreRow: React.FC<ScoreRowProps> = ({ rank, station, isLeader }) => {
  return (
    <tr
      style={{
        borderLeft: isLeader ? '3px solid var(--accent)' : '3px solid transparent',
        background: isLeader
          ? 'linear-gradient(90deg, rgba(244,197,92,0.08) 0%, transparent 60%)'
          : undefined,
        transition: 'background 0.3s ease',
      }}
    >
      {/* Rank */}
      <td
        style={{
          padding: '10px 12px',
          textAlign: 'center',
          fontWeight: 700,
          fontSize: isLeader ? 18 : 14,
          color: isLeader ? 'var(--accent)' : 'var(--text-secondary)',
          width: 48,
        }}
      >
        {isLeader ? (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 2 }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="var(--accent)" style={{ marginRight: 2 }}>
              <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z" />
            </svg>
            {rank}
          </span>
        ) : (
          rank
        )}
      </td>

      {/* Callsign */}
      <td
        className="score-callsign"
        style={{
          padding: '10px 12px',
          fontWeight: 700,
          fontSize: 15,
          letterSpacing: 1,
          fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
          color: isLeader ? 'var(--accent)' : 'var(--text-primary)',
          textShadow: isLeader ? '0 0 12px rgba(244,197,92,0.3)' : 'none',
        }}
      >
        {station.callsign}
      </td>

      {/* Club */}
      <td
        style={{
          padding: '10px 12px',
          color: 'var(--text-secondary)',
          fontSize: 13,
          maxWidth: 140,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
      >
        {station.clubName || '\u2014'}
      </td>

      {/* QSOs */}
      <td
        style={{
          padding: '10px 12px',
          textAlign: 'right',
          fontWeight: 600,
          fontFamily: "'JetBrains Mono', monospace",
          color: 'var(--text-primary)',
          fontSize: 14,
        }}
      >
        {station.totalQsos.toLocaleString()}
      </td>

      {/* Points */}
      <td
        style={{
          padding: '10px 12px',
          textAlign: 'right',
          fontWeight: 700,
          fontFamily: "'JetBrains Mono', monospace",
          color: isLeader ? 'var(--accent)' : 'var(--text-primary)',
          fontSize: 14,
        }}
      >
        {station.totalPoints.toLocaleString()}
      </td>

      {/* Band Breakdown — hidden on mobile via CSS nth-child(6) rule */}
      <td style={{ padding: '10px 12px' }}>
        <BandBreakdown bands={station.bands} />
      </td>

      {/* Rate — hidden on mobile via CSS nth-child(7) rule */}
      <td
        style={{
          padding: '10px 12px',
          textAlign: 'right',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'flex-end',
          gap: 8,
        }}
      >
        <RateGraph data={[station.rate]} />
        <span
          style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 13,
            fontWeight: 600,
            color: station.rate > 0 ? 'var(--accent)' : 'var(--text-secondary)',
            minWidth: 32,
            textAlign: 'right',
          }}
        >
          {station.rate > 0 ? `${station.rate}/h` : '\u2014'}
        </span>
      </td>
    </tr>
  );
};

export default ScoreRow;
