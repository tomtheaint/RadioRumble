import React from 'react';

const BAND_COLORS: Record<string, string> = {
  '160m': '#ff6b6b',
  '80m': '#ee5a24',
  '40m': '#F4C55C',
  '20m': '#7bed9f',
  '15m': '#70a1ff',
  '10m': '#a29bfe',
  '6m': '#fd79a8',
};

const BAND_ORDER = ['160m', '80m', '40m', '20m', '15m', '10m', '6m'];

interface BandBreakdownProps {
  bands: Record<string, number>;
}

const BandBreakdown: React.FC<BandBreakdownProps> = ({ bands }) => {
  const activeBands = BAND_ORDER.filter((b) => (bands[b] || 0) > 0);

  if (activeBands.length === 0) {
    return <span style={{ color: 'var(--text-secondary)', fontSize: 12 }}>—</span>;
  }

  return (
    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
      {activeBands.map((band) => (
        <span
          key={band}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 3,
            padding: '1px 6px',
            borderRadius: 9999,
            fontSize: 11,
            fontWeight: 600,
            letterSpacing: 0.3,
            background: `${BAND_COLORS[band]}22`,
            color: BAND_COLORS[band],
            border: `1px solid ${BAND_COLORS[band]}44`,
          }}
        >
          <span
            style={{
              width: 6,
              height: 6,
              borderRadius: '50%',
              background: BAND_COLORS[band],
              flexShrink: 0,
            }}
          />
          {band.replace('m', '')}
          <span style={{ fontWeight: 700 }}>{bands[band]}</span>
        </span>
      ))}
    </div>
  );
};

export default BandBreakdown;
