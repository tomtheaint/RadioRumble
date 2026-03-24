import React, { useEffect, useState } from 'react';
import { useContestStore } from '../../stores/useContestStore';
import { Contest } from '../../types/contest';
import ClubManager from '../Clubs/ClubManager';

/* ── shared form styles ──────────────────────────────────── */
const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '8px 12px',
  background: 'var(--bg-primary)',
  color: 'var(--text-primary)',
  border: '1px solid var(--border)',
  borderRadius: 'var(--radius-sm)',
  fontSize: 14,
  outline: 'none',
  transition: 'border-color var(--transition-fast)',
};

const labelStyle: React.CSSProperties = {
  display: 'block',
  marginBottom: 4,
  color: 'var(--text-secondary)',
  fontSize: 11,
  fontWeight: 700,
  letterSpacing: '0.06em',
  textTransform: 'uppercase',
};

const btnStyle: React.CSSProperties = {
  padding: '8px 18px',
  background: 'var(--ksu-purple)',
  color: '#fff',
  border: 'none',
  borderRadius: 'var(--radius-sm)',
  fontWeight: 600,
  fontSize: 13,
  cursor: 'pointer',
  transition: 'background var(--transition-fast)',
};

const cardStyle: React.CSSProperties = {
  background: 'var(--bg-card)',
  border: '1px solid var(--border)',
  borderRadius: 'var(--radius-md)',
  padding: 20,
};

/* ── status badge ────────────────────────────────────────── */
const statusColors: Record<string, { bg: string; fg: string }> = {
  pending: { bg: 'rgba(185,171,151,0.15)', fg: 'var(--ksu-tan)' },
  active: { bg: 'rgba(244,197,92,0.18)', fg: 'var(--ksu-gold)' },
  completed: { bg: 'rgba(107,63,160,0.18)', fg: 'var(--ksu-purple-light)' },
};

const StatusBadge: React.FC<{ status: string }> = ({ status }) => {
  const c = statusColors[status] || statusColors.pending;
  return (
    <span
      style={{
        display: 'inline-block',
        padding: '2px 10px',
        borderRadius: 9999,
        fontSize: 11,
        fontWeight: 700,
        letterSpacing: '0.04em',
        textTransform: 'uppercase',
        background: c.bg,
        color: c.fg,
      }}
    >
      {status}
    </span>
  );
};

/* ── format helpers ──────────────────────────────────────── */
function fmtDate(iso?: string) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/* ═══════════════════════════════════════════════════════════
   ContestManager — /manage route
   ═══════════════════════════════════════════════════════════ */
const ContestManager: React.FC = () => {
  const { contests, activeContest, fetchContests, createContest, setActiveContest } =
    useContestStore();

  /* ── create-form local state ── */
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [startTime, setStartTime] = useState('');
  const [endTime, setEndTime] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    useContestStore.getState().fetchContests();
  }, []);

  /* ── handlers ── */
  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setSubmitting(true);
    try {
      await createContest({
        name: name.trim(),
        description: description.trim() || undefined,
        startTime: startTime || undefined,
        endTime: endTime || undefined,
      });
      setName('');
      setDescription('');
      setStartTime('');
      setEndTime('');
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggle = async (contest: Contest) => {
    const next = contest.status === 'active' ? 'completed' : 'active';
    await fetch(`/api/contests/${contest.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: next }),
    });
    await fetchContests();
  };

  const handleDelete = async (id: number) => {
    await fetch(`/api/contests/${id}`, { method: 'DELETE' });
    if (activeContest?.id === id) setActiveContest(null);
    await fetchContests();
  };

  const handleSetActive = (c: Contest) => {
    setActiveContest(c);
  };

  /* ── render ── */
  return (
    <div
      className="manage-grid-mobile"
      style={{
        display: 'grid',
        gridTemplateColumns: 'minmax(0,1fr) minmax(0,1fr)',
        gap: 24,
        padding: 24,
        maxWidth: 1400,
        margin: '0 auto',
      }}
    >
      {/* ───────── Left column ───────── */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
        {/* Create Contest Form */}
        <div style={cardStyle}>
          <h2
            style={{
              margin: '0 0 16px',
              fontSize: 16,
              fontWeight: 700,
              letterSpacing: '0.04em',
              textTransform: 'uppercase',
              color: 'var(--accent)',
            }}
          >
            Create Contest
          </h2>

          <form
            onSubmit={handleCreate}
            style={{ display: 'flex', flexDirection: 'column', gap: 12 }}
          >
            <div>
              <label style={labelStyle}>Name *</label>
              <input
                style={inputStyle}
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Spring Sprint 2026"
                required
                onFocus={(e) => (e.currentTarget.style.borderColor = 'var(--accent)')}
                onBlur={(e) => (e.currentTarget.style.borderColor = 'var(--border)')}
              />
            </div>

            <div>
              <label style={labelStyle}>Description</label>
              <input
                style={inputStyle}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Optional description"
                onFocus={(e) => (e.currentTarget.style.borderColor = 'var(--accent)')}
                onBlur={(e) => (e.currentTarget.style.borderColor = 'var(--border)')}
              />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div>
                <label style={labelStyle}>Start Time</label>
                <input
                  type="datetime-local"
                  style={{ ...inputStyle, colorScheme: 'dark' }}
                  value={startTime}
                  onChange={(e) => setStartTime(e.target.value)}
                  onFocus={(e) => (e.currentTarget.style.borderColor = 'var(--accent)')}
                  onBlur={(e) => (e.currentTarget.style.borderColor = 'var(--border)')}
                />
              </div>
              <div>
                <label style={labelStyle}>End Time</label>
                <input
                  type="datetime-local"
                  style={{ ...inputStyle, colorScheme: 'dark' }}
                  value={endTime}
                  onChange={(e) => setEndTime(e.target.value)}
                  onFocus={(e) => (e.currentTarget.style.borderColor = 'var(--accent)')}
                  onBlur={(e) => (e.currentTarget.style.borderColor = 'var(--border)')}
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={submitting || !name.trim()}
              style={{
                ...btnStyle,
                opacity: submitting || !name.trim() ? 0.5 : 1,
                alignSelf: 'flex-start',
                marginTop: 4,
              }}
              onMouseEnter={(e) =>
                (e.currentTarget.style.background = 'var(--accent)')
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.background = 'var(--ksu-purple)')
              }
            >
              {submitting ? 'Creating...' : 'Create Contest'}
            </button>
          </form>
        </div>

        {/* Contest List */}
        <div style={cardStyle}>
          <h2
            style={{
              margin: '0 0 16px',
              fontSize: 16,
              fontWeight: 700,
              letterSpacing: '0.04em',
              textTransform: 'uppercase',
              color: 'var(--accent)',
            }}
          >
            Contests
          </h2>

          {contests.length === 0 && (
            <p style={{ color: 'var(--text-secondary)', fontSize: 13 }}>
              No contests yet. Create one above.
            </p>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {contests.map((c) => {
              const isActive = activeContest?.id === c.id;
              return (
                <div
                  key={c.id}
                  style={{
                    background: 'var(--bg-primary)',
                    border: isActive
                      ? '2px solid var(--accent)'
                      : '1px solid var(--border)',
                    borderRadius: 'var(--radius-sm)',
                    padding: '12px 16px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 12,
                    flexWrap: 'wrap',
                  }}
                >
                  <div style={{ flex: 1, minWidth: 160 }}>
                    <div
                      style={{
                        fontWeight: 700,
                        fontSize: 14,
                        color: isActive ? 'var(--accent)' : 'var(--text-primary)',
                        marginBottom: 4,
                      }}
                    >
                      {c.name}
                    </div>
                    <div
                      style={{
                        fontSize: 12,
                        color: 'var(--text-secondary)',
                        display: 'flex',
                        gap: 12,
                        flexWrap: 'wrap',
                      }}
                    >
                      <span>{fmtDate(c.startTime)} — {fmtDate(c.endTime)}</span>
                    </div>
                  </div>

                  <StatusBadge status={c.status} />

                  <div style={{ display: 'flex', gap: 6 }}>
                    <button
                      style={{
                        ...btnStyle,
                        padding: '5px 12px',
                        fontSize: 12,
                        background:
                          c.status === 'active'
                            ? 'var(--accent-dark)'
                            : 'var(--ksu-purple)',
                      }}
                      onClick={() => handleToggle(c)}
                      onMouseEnter={(e) =>
                        (e.currentTarget.style.background = 'var(--accent)')
                      }
                      onMouseLeave={(e) =>
                        (e.currentTarget.style.background =
                          c.status === 'active'
                            ? 'var(--accent-dark)'
                            : 'var(--ksu-purple)')
                      }
                    >
                      {c.status === 'active' ? 'Stop' : 'Start'}
                    </button>

                    <button
                      style={{
                        ...btnStyle,
                        padding: '5px 12px',
                        fontSize: 12,
                        background: isActive ? 'var(--accent)' : 'var(--ksu-purple)',
                        color: isActive ? '#1a1028' : '#fff',
                      }}
                      onClick={() => handleSetActive(c)}
                    >
                      {isActive ? 'Active' : 'Set Active'}
                    </button>

                    <button
                      style={{
                        ...btnStyle,
                        padding: '5px 12px',
                        fontSize: 12,
                        background: 'transparent',
                        border: '1px solid var(--border)',
                        color: 'var(--text-secondary)',
                      }}
                      onClick={() => handleDelete(c.id)}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.borderColor = '#e74c3c';
                        e.currentTarget.style.color = '#e74c3c';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.borderColor = 'var(--border)';
                        e.currentTarget.style.color = 'var(--text-secondary)';
                      }}
                    >
                      Delete
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* ───────── Right column ───────── */}
      <div>
        {activeContest ? (
          <ClubManager contestId={activeContest.id} />
        ) : (
          <div
            style={{
              ...cardStyle,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              minHeight: 200,
              color: 'var(--text-secondary)',
              fontSize: 14,
            }}
          >
            Select a contest to manage clubs and operators.
          </div>
        )}
      </div>
    </div>
  );
};

export default ContestManager;

// Mobile style injection
if (typeof document !== 'undefined') {
  const styleId = 'manage-mobile-styles';
  if (!document.getElementById(styleId)) {
    const style = document.createElement('style');
    style.id = styleId;
    style.textContent = `
      @media (max-width: 768px) {
        .manage-grid-mobile {
          grid-template-columns: 1fr !important;
          padding: 14px !important;
          gap: 16px !important;
        }
      }
    `;
    document.head.appendChild(style);
  }
}
