import { formatNumber } from '../../utils/formatters';

interface BandChartProps {
  data: Record<string, number>;
}

const BAND_COLORS: Record<string, string> = {
  '160m': '#ff6b6b',
  '80m': '#ee5a24',
  '60m': '#f0932b',
  '40m': '#F4C55C',
  '30m': '#7bed9f',
  '20m': '#70a1ff',
  '17m': '#a29bfe',
  '15m': '#6c5ce7',
  '12m': '#fd79a8',
  '10m': '#e17055',
  '6m': '#00cec9',
  '2m': '#55a3e8',
};

function getBandColor(band: string): string {
  const key = band.toLowerCase().replace(/\s/g, '');
  return BAND_COLORS[key] || '#888';
}

export default function BandChart({ data }: BandChartProps) {
  const entries = Object.entries(data).sort((a, b) => b[1] - a[1]);

  if (entries.length === 0) {
    return <div style={{ color: '#E7DED0', opacity: 0.5 }}>No band data available</div>;
  }

  const max = entries[0][1];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {entries.map(([band, count]) => {
        const pct = max > 0 ? (count / max) * 100 : 0;
        const color = getBandColor(band);

        return (
          <div key={band} style={styles.row}>
            <div style={styles.label}>{band}</div>
            <div style={styles.barTrack}>
              <div
                style={{
                  ...styles.barFill,
                  width: `${pct}%`,
                  background: color,
                }}
              />
            </div>
            <div style={styles.count}>{formatNumber(count)}</div>
          </div>
        );
      })}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  row: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
  },
  label: {
    width: 44,
    fontSize: 13,
    fontWeight: 600,
    color: '#E7DED0',
    textAlign: 'right',
    flexShrink: 0,
  },
  barTrack: {
    flex: 1,
    height: 20,
    background: 'rgba(255,255,255,0.05)',
    borderRadius: 4,
    overflow: 'hidden',
  },
  barFill: {
    height: '100%',
    borderRadius: 4,
    transition: 'width 0.4s ease',
    minWidth: 2,
  },
  count: {
    width: 52,
    fontSize: 13,
    color: '#E7DED0',
    textAlign: 'right',
    flexShrink: 0,
  },
};
