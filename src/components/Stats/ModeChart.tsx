import { formatNumber } from '../../utils/formatters';

interface ModeChartProps {
  data: Record<string, number>;
}

const MODE_COLORS: Record<string, string> = {
  FT8: '#F4C55C',
  FT4: '#CEA152',
  CW: '#70a1ff',
  SSB: '#7bed9f',
  RTTY: '#a29bfe',
};

function getModeColor(mode: string): string {
  return MODE_COLORS[mode.toUpperCase()] || '#888';
}

export default function ModeChart({ data }: ModeChartProps) {
  const entries = Object.entries(data).filter(([, v]) => v > 0);
  const total = entries.reduce((sum, [, v]) => sum + v, 0);

  if (entries.length === 0 || total === 0) {
    return <div style={{ color: '#E7DED0', opacity: 0.5 }}>No mode data available</div>;
  }

  // Build conic-gradient segments
  let cumPct = 0;
  const segments: string[] = [];
  entries.forEach(([mode, count]) => {
    const pct = (count / total) * 100;
    const color = getModeColor(mode);
    segments.push(`${color} ${cumPct}% ${cumPct + pct}%`);
    cumPct += pct;
  });

  const gradient = `conic-gradient(${segments.join(', ')})`;

  return (
    <div style={styles.wrapper}>
      <div style={styles.chartArea}>
        <div style={{ ...styles.donut, background: gradient }}>
          <div style={styles.donutCenter}>
            <div style={styles.totalNumber}>{formatNumber(total)}</div>
            <div style={styles.totalLabel}>QSOs</div>
          </div>
        </div>
      </div>
      <div style={styles.legend}>
        {entries.map(([mode, count]) => {
          const pct = ((count / total) * 100).toFixed(1);
          return (
            <div key={mode} style={styles.legendItem}>
              <div style={{ ...styles.legendDot, background: getModeColor(mode) }} />
              <span style={styles.legendMode}>{mode}</span>
              <span style={styles.legendCount}>
                {formatNumber(count)} ({pct}%)
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  wrapper: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 16,
  },
  chartArea: {
    display: 'flex',
    justifyContent: 'center',
  },
  donut: {
    width: 180,
    height: 180,
    borderRadius: '50%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  donutCenter: {
    width: 100,
    height: 100,
    borderRadius: '50%',
    background: '#2d1d42',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
  },
  totalNumber: {
    fontSize: 22,
    fontWeight: 700,
    color: '#F4C55C',
  },
  totalLabel: {
    fontSize: 11,
    color: '#E7DED0',
    opacity: 0.7,
    textTransform: 'uppercase' as const,
    letterSpacing: '1px',
  },
  legend: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: 12,
    justifyContent: 'center',
  },
  legendItem: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    fontSize: 13,
  },
  legendDot: {
    width: 10,
    height: 10,
    borderRadius: '50%',
    flexShrink: 0,
  },
  legendMode: {
    fontWeight: 600,
    color: '#E7DED0',
  },
  legendCount: {
    color: '#E7DED0',
    opacity: 0.7,
  },
};
