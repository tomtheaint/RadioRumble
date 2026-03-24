import React, { useRef, useEffect, useState } from 'react';
import { useQsoStore } from '../../stores/useQsoStore';

const BAND_COLORS: Record<string, string> = {
  '160m': '#ff6b6b',
  '80m': '#ee5a24',
  '40m': '#F4C55C',
  '20m': '#7bed9f',
  '15m': '#70a1ff',
  '10m': '#a29bfe',
  '6m': '#fd79a8',
};

const MODE_COLORS: Record<string, string> = {
  CW: '#70a1ff',
  SSB: '#7bed9f',
  FT8: '#a29bfe',
  FT4: '#fd79a8',
  RTTY: '#F4C55C',
  AM: '#ff6b6b',
  FM: '#ee5a24',
};

function formatTime(dateStr: string): string {
  try {
    const d = new Date(dateStr);
    return d.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    });
  } catch {
    return '--:--:--';
  }
}

const QsoFeed: React.FC = () => {
  const recentQsos = useQsoStore((s) => s.recentQsos);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [flashId, setFlashId] = useState<number | null>(null);
  const prevCountRef = useRef(recentQsos.length);

  useEffect(() => {
    if (recentQsos.length > prevCountRef.current && recentQsos.length > 0) {
      const newest = recentQsos[0];
      setFlashId(newest.id);
      const timer = setTimeout(() => setFlashId(null), 800);
      return () => clearTimeout(timer);
    }
    prevCountRef.current = recentQsos.length;
  }, [recentQsos]);

  return (
    <div
      style={{
        background: 'var(--bg-card)',
        border: '1px solid var(--border)',
        borderRadius: 12,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        height: '100%',
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: '12px 16px',
          borderBottom: '1px solid var(--border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexShrink: 0,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              background: '#00c853',
              boxShadow: '0 0 8px #00c85366',
              animation: 'feed-pulse 2s ease-in-out infinite',
              flexShrink: 0,
            }}
          />
          <h2
            style={{
              margin: 0,
              fontSize: 12,
              fontWeight: 800,
              color: 'var(--text-secondary)',
              textTransform: 'uppercase',
              letterSpacing: 2,
            }}
          >
            Live Feed
          </h2>
        </div>
        <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
          {recentQsos.length} QSO{recentQsos.length !== 1 ? 's' : ''}
        </span>
      </div>

      {/* Feed List */}
      <div
        ref={scrollRef}
        style={{
          flex: 1,
          overflowY: 'auto',
          overflowX: 'hidden',
          minHeight: 0,
        }}
      >
        {recentQsos.length === 0 ? (
          <div
            style={{
              padding: '40px 16px',
              textAlign: 'center',
              color: 'var(--text-secondary)',
              fontSize: 13,
              opacity: 0.6,
            }}
          >
            Waiting for QSOs...
          </div>
        ) : (
          recentQsos.map((qso) => {
            const isFlashing = flashId === qso.id;
            const bandColor = BAND_COLORS[qso.band] || 'var(--text-secondary)';
            const modeColor = MODE_COLORS[qso.mode] || 'var(--text-secondary)';

            return (
              <div
                key={qso.id}
                className="qso-entry-mobile"
                style={{
                  padding: '8px 16px',
                  borderBottom: '1px solid var(--border)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  fontSize: 13,
                  transition: 'background 0.4s ease',
                  background: isFlashing
                    ? 'rgba(244,197,92,0.12)'
                    : 'transparent',
                  animation: isFlashing ? 'qso-flash 0.8s ease-out' : 'none',
                }}
              >
                {/* Time */}
                <span
                  style={{
                    fontFamily: "'JetBrains Mono', monospace",
                    fontSize: 11,
                    color: 'var(--text-secondary)',
                    flexShrink: 0,
                    width: 62,
                  }}
                >
                  {formatTime(qso.createdAt)}
                </span>

                {/* Station → Call */}
                <div
                  style={{
                    flex: 1,
                    minWidth: 0,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 4,
                    overflow: 'hidden',
                  }}
                >
                  <span
                    style={{
                      fontWeight: 700,
                      color: 'var(--accent)',
                      fontFamily: "'JetBrains Mono', monospace",
                      fontSize: 12,
                      flexShrink: 0,
                    }}
                  >
                    {qso.stationCallsign}
                  </span>
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="var(--text-secondary)" style={{ flexShrink: 0, opacity: 0.5 }}>
                    <path d="M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z" />
                  </svg>
                  <span
                    style={{
                      fontWeight: 600,
                      color: 'var(--text-primary)',
                      fontFamily: "'JetBrains Mono', monospace",
                      fontSize: 12,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {qso.call}
                  </span>
                </div>

                {/* Band */}
                <span
                  style={{
                    padding: '1px 7px',
                    borderRadius: 9999,
                    fontSize: 10,
                    fontWeight: 700,
                    background: `${bandColor}22`,
                    color: bandColor,
                    border: `1px solid ${bandColor}44`,
                    flexShrink: 0,
                    letterSpacing: 0.3,
                  }}
                >
                  {qso.band}
                </span>

                {/* Mode */}
                <span
                  style={{
                    padding: '1px 6px',
                    borderRadius: 4,
                    fontSize: 10,
                    fontWeight: 700,
                    background: `${modeColor}18`,
                    color: modeColor,
                    flexShrink: 0,
                    letterSpacing: 0.5,
                  }}
                >
                  {qso.mode}
                </span>

                {/* Grid */}
                {qso.gridsquare && (
                  <span
                    style={{
                      fontSize: 10,
                      color: 'var(--text-secondary)',
                      fontFamily: "'JetBrains Mono', monospace",
                      flexShrink: 0,
                      opacity: 0.7,
                    }}
                  >
                    {qso.gridsquare}
                  </span>
                )}

                {/* Multiplier badge */}
                {qso.isMultiplier && (
                  <span
                    style={{
                      fontSize: 9,
                      fontWeight: 800,
                      color: '#ff6b6b',
                      background: 'rgba(255,107,107,0.15)',
                      padding: '1px 5px',
                      borderRadius: 4,
                      letterSpacing: 0.5,
                      flexShrink: 0,
                    }}
                  >
                    MULT
                  </span>
                )}
              </div>
            );
          })
        )}
      </div>

      <style>{`
        @keyframes feed-pulse {
          0%, 100% { opacity: 1; box-shadow: 0 0 8px #00c85366; }
          50% { opacity: 0.4; box-shadow: 0 0 4px #00c85322; }
        }
        @keyframes qso-flash {
          0% { background: rgba(244,197,92,0.25); }
          100% { background: transparent; }
        }
        @media (max-width: 768px) {
          .qso-entry-mobile {
            padding: 6px 10px !important;
            gap: 6px !important;
            font-size: 12px !important;
          }
        }
      `}</style>
    </div>
  );
};

export default QsoFeed;
