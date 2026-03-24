import { useState, lazy, Suspense } from 'react';
import QsoMap from './QsoMap';

const QsoGlobe = lazy(() => import('./QsoGlobe'));

type ViewMode = '2d' | '3d';

export default function MapPage() {
  const [view, setView] = useState<ViewMode>('2d');

  return (
    <div style={styles.wrapper}>
      {/* Toggle pills */}
      <div style={styles.toggleBar}>
        <button
          style={{
            ...styles.pill,
            ...(view === '2d' ? styles.pillActive : styles.pillInactive),
            borderRadius: '6px 0 0 6px',
          }}
          onClick={() => setView('2d')}
        >
          2D Map
        </button>
        <button
          style={{
            ...styles.pill,
            ...(view === '3d' ? styles.pillActive : styles.pillInactive),
            borderRadius: '0 6px 6px 0',
          }}
          onClick={() => setView('3d')}
        >
          3D Globe
        </button>
      </div>

      {/* Map / Globe content */}
      <div style={styles.content}>
        {view === '2d' ? (
          <QsoMap />
        ) : (
          <Suspense
            fallback={
              <div style={styles.fallback}>Loading globe...</div>
            }
          >
            <QsoGlobe />
          </Suspense>
        )}
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  wrapper: {
    display: 'flex',
    flexDirection: 'column',
    height: '100%',
    background: '#1a1028',
  },
  toggleBar: {
    display: 'flex',
    justifyContent: 'center',
    padding: '10px 0 6px',
    background: '#1a1028',
    flexShrink: 0,
  },
  pill: {
    padding: '7px 22px',
    fontSize: 14,
    fontWeight: 600,
    border: '1px solid #512888',
    cursor: 'pointer',
    transition: 'all 0.15s ease',
    letterSpacing: '0.02em',
  },
  pillActive: {
    background: '#F4C55C',
    color: '#1a1028',
    borderColor: '#F4C55C',
  },
  pillInactive: {
    background: '#2d1d42',
    color: '#E7DED0',
    borderColor: '#3a2a52',
  },
  content: {
    flex: 1,
    position: 'relative' as const,
    overflow: 'hidden',
  },
  fallback: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    height: '100%',
    color: '#E7DED0',
    fontSize: 16,
    background: '#1a1028',
  },
};
