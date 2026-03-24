import { formatNumber } from '../../utils/formatters';

interface MultiplierTrackerProps {
  grids: string[];
}

export default function MultiplierTracker({ grids }: MultiplierTrackerProps) {
  const sorted = [...grids].sort();

  return (
    <div style={styles.wrapper}>
      <div style={styles.countSection}>
        <div style={styles.countNumber}>{formatNumber(grids.length)}</div>
        <div style={styles.countLabel}>unique grids worked</div>
      </div>
      {sorted.length > 0 && (
        <div style={styles.gridList}>
          {sorted.map((grid) => (
            <span key={grid} style={styles.pill}>
              {grid.toUpperCase()}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  wrapper: {
    display: 'flex',
    flexDirection: 'column',
    gap: 16,
  },
  countSection: {
    textAlign: 'center',
  },
  countNumber: {
    fontSize: 42,
    fontWeight: 700,
    color: '#F4C55C',
    lineHeight: 1,
  },
  countLabel: {
    fontSize: 13,
    color: '#E7DED0',
    opacity: 0.6,
    marginTop: 4,
    textTransform: 'uppercase' as const,
    letterSpacing: '0.5px',
  },
  gridList: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: 6,
    maxHeight: 180,
    overflowY: 'auto',
    padding: '4px 0',
  },
  pill: {
    display: 'inline-block',
    background: '#512888',
    color: '#E7DED0',
    fontSize: 11,
    fontWeight: 600,
    padding: '3px 8px',
    borderRadius: 12,
    letterSpacing: '0.3px',
  },
};
