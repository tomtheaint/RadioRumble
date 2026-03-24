import { useEffect } from 'react';
import { useContestStore } from '../../stores/useContestStore';
import { useWebSocketStore } from '../../stores/useWebSocketStore';

function formatTime(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

export default function Header() {
  const { activeContest, contests, elapsed, remaining, status, fetchContests, setActiveContest } = useContestStore();
  const connected = useWebSocketStore((s) => s.connected);

  useEffect(() => {
    const { fetchContests } = useContestStore.getState();
    fetchContests().then(() => {
      const { contests } = useContestStore.getState();
      const active = contests.find((c) => c.status === 'active') || contests[0];
      if (active) useContestStore.getState().setActiveContest(active);
    });
  }, []);

  return (
    <header className="header-mobile" style={styles.header}>
      {/* Left — branding */}
      <div style={styles.left}>
        <span style={styles.icon}>&#x26A1;</span>
        <span className="header-title" style={styles.title}>RADIORUMBLE</span>
      </div>

      {/* Center — contest info (hidden on very small screens via CSS) */}
      <div className="header-center" style={styles.center}>
        {activeContest ? (
          <>
            <span style={styles.contestName}>{activeContest.name}</span>
            <span className="header-timer" style={styles.timer}>
              {status === 'active' && (
                <>
                  <span style={styles.timerLabel}>ELAPSED</span>
                  <span style={styles.timerValue}>{formatTime(elapsed)}</span>
                  {remaining !== null && (
                    <>
                      <span style={styles.timerSep}>|</span>
                      <span style={styles.timerLabel}>LEFT</span>
                      <span style={styles.timerValue}>
                        {formatTime(remaining)}
                      </span>
                    </>
                  )}
                </>
              )}
              {status === 'pending' && (
                <span style={styles.statusPill}>PENDING</span>
              )}
              {status === 'completed' && (
                <span style={{ ...styles.statusPill, background: '#2a6e2a' }}>
                  COMPLETE
                </span>
              )}
            </span>
          </>
        ) : (
          <span style={styles.noContest}>No active contest</span>
        )}
      </div>

      {/* Right — connection + KSU badge */}
      <div style={styles.right}>
        <span
          style={{
            ...styles.dot,
            background: connected ? '#4ade80' : '#ef4444',
            boxShadow: connected
              ? '0 0 6px rgba(74,222,128,0.5)'
              : '0 0 6px rgba(239,68,68,0.5)',
          }}
          title={connected ? 'Connected' : 'Disconnected'}
        />
        <span className="header-badge" style={styles.badge}>KSU</span>
      </div>

      <style>{`
        @media (max-width: 768px) {
          .header-center {
            display: none !important;
          }
          .header-title {
            font-size: 14px !important;
          }
          .header-badge {
            font-size: 11px !important;
            padding: 1px 6px !important;
          }
        }
        @media (min-width: 481px) and (max-width: 768px) {
          .header-center {
            display: flex !important;
          }
          .header-timer {
            display: none !important;
          }
        }
      `}</style>
    </header>
  );
}

const styles: Record<string, React.CSSProperties> = {
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    height: 56,
    padding: '0 20px',
    background: '#512888',
    flexShrink: 0,
    borderBottom: '2px solid #6b3fa0',
  },

  /* Left */
  left: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
  },
  icon: {
    fontSize: 20,
    lineHeight: 1,
  },
  title: {
    fontWeight: 800,
    fontSize: 18,
    letterSpacing: '0.08em',
    color: '#ffffff',
  },

  /* Center */
  center: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 2,
  },
  contestName: {
    fontWeight: 600,
    fontSize: 14,
    color: '#F4C55C',
    letterSpacing: '0.02em',
  },
  timer: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    fontSize: 12,
  },
  timerLabel: {
    color: 'rgba(255,255,255,0.5)',
    fontWeight: 600,
    fontSize: 10,
    letterSpacing: '0.06em',
  },
  timerValue: {
    color: '#ffffff',
    fontFamily: "'JetBrains Mono', monospace",
    fontWeight: 600,
    fontSize: 13,
  },
  timerSep: {
    color: 'rgba(255,255,255,0.25)',
    margin: '0 2px',
  },
  statusPill: {
    fontSize: 10,
    fontWeight: 700,
    letterSpacing: '0.06em',
    padding: '2px 8px',
    borderRadius: 4,
    background: '#CEA152',
    color: '#1a1028',
  },
  noContest: {
    color: 'rgba(255,255,255,0.4)',
    fontSize: 13,
    fontStyle: 'italic',
  },

  /* Right */
  right: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: '50%',
    display: 'inline-block',
    boxShadow: '0 0 6px rgba(74,222,128,0.5)',
  },
  badge: {
    fontWeight: 800,
    fontSize: 13,
    letterSpacing: '0.12em',
    color: '#F4C55C',
    border: '1.5px solid #F4C55C',
    borderRadius: 4,
    padding: '2px 8px',
    lineHeight: 1,
  },
};
