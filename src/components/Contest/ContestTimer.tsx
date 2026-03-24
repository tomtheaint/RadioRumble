import React, { useEffect, useState, useRef } from 'react';

/* ── helpers ─────────────────────────────────────────────── */
function pad(n: number): string {
  return String(n).padStart(2, '0');
}

function formatDuration(totalSeconds: number): string {
  const h = Math.floor(totalSeconds / 3600);
  const m = Math.floor((totalSeconds % 3600) / 60);
  const s = totalSeconds % 60;
  return `${pad(h)}:${pad(m)}:${pad(s)}`;
}

/* ── props ───────────────────────────────────────────────── */
interface ContestTimerProps {
  startTime: string;
  endTime: string | null;
  status: string;
}

/* ═══════════════════════════════════════════════════════════
   ContestTimer — live countdown / elapsed timer
   ═══════════════════════════════════════════════════════════ */
const ContestTimer: React.FC<ContestTimerProps> = ({ startTime, endTime, status }) => {
  const [now, setNow] = useState(Date.now());
  const rafRef = useRef<ReturnType<typeof setInterval>>();

  useEffect(() => {
    rafRef.current = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(rafRef.current);
  }, []);

  const startMs = new Date(startTime).getTime();
  const endMs = endTime ? new Date(endTime).getTime() : null;

  /* ── compute display values ── */
  let primaryLabel = '';
  let primaryValue = '';
  let secondaryLabel = '';
  let secondaryValue = '';
  let color = 'var(--text-primary)';

  if (status === 'active') {
    const elapsed = Math.max(0, Math.floor((now - startMs) / 1000));
    primaryLabel = 'ELAPSED';
    primaryValue = formatDuration(elapsed);
    color = 'var(--accent)';

    if (endMs !== null) {
      const remaining = Math.max(0, Math.floor((endMs - now) / 1000));
      secondaryLabel = 'REMAINING';
      secondaryValue = formatDuration(remaining);
    }
  } else if (status === 'pending') {
    const until = Math.max(0, Math.floor((startMs - now) / 1000));
    primaryLabel = 'STARTS IN';
    primaryValue = formatDuration(until);
    color = 'var(--text-secondary)';
  } else {
    /* completed */
    const total = endMs
      ? Math.max(0, Math.floor((endMs - startMs) / 1000))
      : Math.max(0, Math.floor((now - startMs) / 1000));
    primaryLabel = 'CONTEST ENDED';
    primaryValue = formatDuration(total);
    color = 'var(--ksu-purple-light)';
  }

  /* ── render ── */
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'baseline',
        gap: 28,
        flexWrap: 'wrap',
      }}
    >
      {/* Primary timer */}
      <div style={{ textAlign: 'center' }}>
        <div
          style={{
            fontSize: 11,
            fontWeight: 700,
            letterSpacing: '0.08em',
            textTransform: 'uppercase',
            color: 'var(--text-secondary)',
            marginBottom: 2,
          }}
        >
          {primaryLabel}
        </div>
        <div
          style={{
            fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
            fontSize: 38,
            fontWeight: 700,
            letterSpacing: 2,
            lineHeight: 1,
            color,
            textShadow:
              status === 'active' ? '0 0 18px rgba(244,197,92,0.35)' : 'none',
          }}
        >
          {primaryValue}
        </div>
      </div>

      {/* Secondary timer (remaining) */}
      {secondaryValue && (
        <div style={{ textAlign: 'center' }}>
          <div
            style={{
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              color: 'var(--text-secondary)',
              marginBottom: 2,
            }}
          >
            {secondaryLabel}
          </div>
          <div
            style={{
              fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
              fontSize: 28,
              fontWeight: 600,
              letterSpacing: 2,
              lineHeight: 1,
              color: 'var(--text-primary)',
            }}
          >
            {secondaryValue}
          </div>
        </div>
      )}
    </div>
  );
};

export default ContestTimer;
