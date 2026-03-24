import React, { useCallback, useEffect, useState } from 'react';
import { Club, Operator } from '../../types/club';

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

/* ── props ───────────────────────────────────────────────── */
interface ClubManagerProps {
  contestId: number;
}

/* ═══════════════════════════════════════════════════════════
   ClubManager — club / team management panel
   ═══════════════════════════════════════════════════════════ */
const ClubManager: React.FC<ClubManagerProps> = ({ contestId }) => {
  const [clubs, setClubs] = useState<Club[]>([]);
  const [operators, setOperators] = useState<Record<number, Operator[]>>({});
  const [expanded, setExpanded] = useState<number | null>(null);
  const [clubName, setClubName] = useState('');
  const [clubCallsign, setClubCallsign] = useState('');
  const [addingClub, setAddingClub] = useState(false);

  /* per-club "add operator" callsign input */
  const [opCallsigns, setOpCallsigns] = useState<Record<number, string>>({});

  /* ── fetch clubs ── */
  const fetchClubs = useCallback(async () => {
    const res = await fetch(`/api/contests/${contestId}/clubs`);
    const data: Club[] = await res.json();
    setClubs(data);
  }, [contestId]);

  useEffect(() => {
    fetchClubs();
  }, [fetchClubs]);

  /* ── fetch operators for a club (extracted from clubs endpoint) ── */
  const fetchOperators = useCallback(
    async (clubId: number) => {
      const res = await fetch(`/api/contests/${contestId}/clubs`);
      const data: Club[] = await res.json();
      const club = data.find((c) => c.id === clubId);
      setOperators((prev) => ({ ...prev, [clubId]: club?.operators || [] }));
    },
    [contestId]
  );

  /* ── handlers ── */
  const handleAddClub = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!clubName.trim() || !clubCallsign.trim()) return;
    setAddingClub(true);
    try {
      await fetch(`/api/contests/${contestId}/clubs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: clubName.trim(),
          callsign: clubCallsign.trim().toUpperCase(),
        }),
      });
      setClubName('');
      setClubCallsign('');
      await fetchClubs();
    } finally {
      setAddingClub(false);
    }
  };

  const handleDeleteClub = async (clubId: number) => {
    await fetch(`/api/clubs/${clubId}`, {
      method: 'DELETE',
    });
    if (expanded === clubId) setExpanded(null);
    await fetchClubs();
  };

  const handleToggle = async (clubId: number) => {
    if (expanded === clubId) {
      setExpanded(null);
    } else {
      setExpanded(clubId);
      await fetchOperators(clubId);
    }
  };

  const handleAddOperator = async (clubId: number) => {
    const callsign = (opCallsigns[clubId] || '').trim().toUpperCase();
    if (!callsign) return;
    await fetch(`/api/clubs/${clubId}/operators`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ callsign }),
    });
    setOpCallsigns((prev) => ({ ...prev, [clubId]: '' }));
    await fetchOperators(clubId);
  };

  const handleDeleteOperator = async (clubId: number, opId: number) => {
    await fetch(`/api/operators/${opId}`, { method: 'DELETE' });
    await fetchOperators(clubId);
  };

  /* ── render ── */
  return (
    <div style={{ ...cardStyle, display: 'flex', flexDirection: 'column', gap: 20 }}>
      <h2
        style={{
          margin: 0,
          fontSize: 16,
          fontWeight: 700,
          letterSpacing: '0.04em',
          textTransform: 'uppercase',
          color: 'var(--accent)',
        }}
      >
        Club / Team Management
      </h2>

      {/* Add Club form */}
      <form
        onSubmit={handleAddClub}
        style={{ display: 'flex', gap: 10, alignItems: 'flex-end', flexWrap: 'wrap' }}
      >
        <div style={{ flex: 1, minWidth: 140 }}>
          <label style={labelStyle}>Club Name *</label>
          <input
            style={inputStyle}
            value={clubName}
            onChange={(e) => setClubName(e.target.value)}
            placeholder="K-State ARC"
            required
            onFocus={(e) => (e.currentTarget.style.borderColor = 'var(--accent)')}
            onBlur={(e) => (e.currentTarget.style.borderColor = 'var(--border)')}
          />
        </div>
        <div style={{ width: 130 }}>
          <label style={labelStyle}>Callsign *</label>
          <input
            style={{ ...inputStyle, textTransform: 'uppercase' }}
            value={clubCallsign}
            onChange={(e) => setClubCallsign(e.target.value)}
            placeholder="W0QQQ"
            required
            onFocus={(e) => (e.currentTarget.style.borderColor = 'var(--accent)')}
            onBlur={(e) => (e.currentTarget.style.borderColor = 'var(--border)')}
          />
        </div>
        <button
          type="submit"
          disabled={addingClub || !clubName.trim() || !clubCallsign.trim()}
          style={{
            ...btnStyle,
            opacity: addingClub || !clubName.trim() || !clubCallsign.trim() ? 0.5 : 1,
          }}
          onMouseEnter={(e) =>
            (e.currentTarget.style.background = 'var(--accent)')
          }
          onMouseLeave={(e) =>
            (e.currentTarget.style.background = 'var(--ksu-purple)')
          }
        >
          Add Club
        </button>
      </form>

      {/* Club list */}
      {clubs.length === 0 && (
        <p style={{ color: 'var(--text-secondary)', fontSize: 13 }}>
          No clubs yet for this contest.
        </p>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {clubs.map((club) => {
          const isOpen = expanded === club.id;
          const ops = operators[club.id] || [];

          return (
            <div
              key={club.id}
              style={{
                background: 'var(--bg-primary)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-sm)',
                overflow: 'hidden',
              }}
            >
              {/* Club header row */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  padding: '10px 14px',
                  cursor: 'pointer',
                }}
                onClick={() => handleToggle(club.id)}
              >
                {/* Expand chevron */}
                <span
                  style={{
                    fontSize: 12,
                    color: 'var(--text-secondary)',
                    transform: isOpen ? 'rotate(90deg)' : 'rotate(0)',
                    transition: 'transform var(--transition-fast)',
                    display: 'inline-block',
                    width: 14,
                    textAlign: 'center',
                  }}
                >
                  &#9654;
                </span>

                <span style={{ fontWeight: 700, fontSize: 14, flex: 1 }}>
                  {club.name}
                </span>

                {club.callsign && (
                  <span
                    style={{
                      fontFamily: "'JetBrains Mono', monospace",
                      fontSize: 12,
                      color: 'var(--accent)',
                      fontWeight: 600,
                      letterSpacing: 0.5,
                    }}
                  >
                    {club.callsign}
                  </span>
                )}

                <span
                  style={{
                    fontSize: 12,
                    color: 'var(--text-secondary)',
                    minWidth: 70,
                    textAlign: 'right',
                  }}
                >
                  {ops.length || '—'} ops
                </span>

                {/* Delete club */}
                <button
                  style={{
                    background: 'transparent',
                    border: '1px solid var(--border)',
                    color: 'var(--text-secondary)',
                    borderRadius: 'var(--radius-sm)',
                    padding: '3px 8px',
                    fontSize: 11,
                    cursor: 'pointer',
                    transition: 'all var(--transition-fast)',
                  }}
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDeleteClub(club.id);
                  }}
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

              {/* Expanded operator list */}
              {isOpen && (
                <div
                  style={{
                    borderTop: '1px solid var(--border)',
                    padding: '10px 14px 14px 38px',
                  }}
                >
                  {/* Operator list */}
                  {ops.length === 0 ? (
                    <p
                      style={{
                        fontSize: 12,
                        color: 'var(--text-secondary)',
                        marginBottom: 8,
                      }}
                    >
                      No operators yet.
                    </p>
                  ) : (
                    <div
                      style={{
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 4,
                        marginBottom: 10,
                      }}
                    >
                      {ops.map((op) => (
                        <div
                          key={op.id}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 8,
                          }}
                        >
                          <span
                            style={{
                              fontFamily: "'JetBrains Mono', monospace",
                              fontSize: 13,
                              fontWeight: 600,
                              letterSpacing: 0.5,
                              color: 'var(--text-primary)',
                            }}
                          >
                            {op.callsign}
                          </span>
                          <button
                            style={{
                              background: 'transparent',
                              border: 'none',
                              color: 'var(--text-secondary)',
                              fontSize: 11,
                              cursor: 'pointer',
                              padding: '2px 6px',
                            }}
                            onClick={() => handleDeleteOperator(club.id, op.id)}
                            onMouseEnter={(e) =>
                              (e.currentTarget.style.color = '#e74c3c')
                            }
                            onMouseLeave={(e) =>
                              (e.currentTarget.style.color = 'var(--text-secondary)')
                            }
                          >
                            remove
                          </button>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Add operator inline */}
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <input
                      style={{
                        ...inputStyle,
                        maxWidth: 160,
                        padding: '5px 10px',
                        fontSize: 13,
                        textTransform: 'uppercase',
                      }}
                      placeholder="Callsign"
                      value={opCallsigns[club.id] || ''}
                      onChange={(e) =>
                        setOpCallsigns((prev) => ({
                          ...prev,
                          [club.id]: e.target.value,
                        }))
                      }
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          e.preventDefault();
                          handleAddOperator(club.id);
                        }
                      }}
                      onFocus={(e) =>
                        (e.currentTarget.style.borderColor = 'var(--accent)')
                      }
                      onBlur={(e) =>
                        (e.currentTarget.style.borderColor = 'var(--border)')
                      }
                    />
                    <button
                      style={{
                        ...btnStyle,
                        padding: '5px 12px',
                        fontSize: 12,
                      }}
                      onClick={() => handleAddOperator(club.id)}
                      onMouseEnter={(e) =>
                        (e.currentTarget.style.background = 'var(--accent)')
                      }
                      onMouseLeave={(e) =>
                        (e.currentTarget.style.background = 'var(--ksu-purple)')
                      }
                    >
                      Add Operator
                    </button>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default ClubManager;
