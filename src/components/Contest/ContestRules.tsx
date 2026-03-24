import React, { useEffect, useState } from 'react';

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

/* ── types ───────────────────────────────────────────────── */
interface ScoringRules {
  pointsPerQso: number;
  multiplierType: 'grid_squares' | 'dxcc' | 'none';
  bandBonuses: Record<string, number>;
}

const DEFAULT_RULES: ScoringRules = {
  pointsPerQso: 1,
  multiplierType: 'none',
  bandBonuses: {},
};

const BANDS = ['160m', '80m', '40m', '20m', '15m', '10m', '6m'];

/* ── props ───────────────────────────────────────────────── */
interface ContestRulesProps {
  contestId: number;
  currentRules: string;
}

/* ═══════════════════════════════════════════════════════════
   ContestRules — scoring rules config
   ═══════════════════════════════════════════════════════════ */
const ContestRules: React.FC<ContestRulesProps> = ({ contestId, currentRules }) => {
  const [rules, setRules] = useState<ScoringRules>(DEFAULT_RULES);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  /* Parse incoming rules JSON on mount / prop change */
  useEffect(() => {
    try {
      const parsed = JSON.parse(currentRules);
      setRules({ ...DEFAULT_RULES, ...parsed });
    } catch {
      setRules(DEFAULT_RULES);
    }
  }, [currentRules]);

  const handleBandBonus = (band: string, value: string) => {
    const n = parseFloat(value);
    setRules((prev) => ({
      ...prev,
      bandBonuses: {
        ...prev.bandBonuses,
        [band]: isNaN(n) ? 1 : n,
      },
    }));
  };

  const handleSave = async () => {
    setSaving(true);
    setSaved(false);
    try {
      await fetch(`/api/contests/${contestId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rules: JSON.stringify(rules) }),
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } finally {
      setSaving(false);
    }
  };

  return (
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
        Scoring Rules
      </h2>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {/* Points per QSO */}
        <div>
          <label style={labelStyle}>Points Per QSO</label>
          <input
            type="number"
            min={0}
            step={1}
            style={{ ...inputStyle, maxWidth: 120 }}
            value={rules.pointsPerQso}
            onChange={(e) =>
              setRules((p) => ({
                ...p,
                pointsPerQso: parseInt(e.target.value, 10) || 0,
              }))
            }
            onFocus={(e) => (e.currentTarget.style.borderColor = 'var(--accent)')}
            onBlur={(e) => (e.currentTarget.style.borderColor = 'var(--border)')}
          />
        </div>

        {/* Multiplier type */}
        <div>
          <label style={labelStyle}>Multiplier Type</label>
          <select
            style={{
              ...inputStyle,
              maxWidth: 220,
              cursor: 'pointer',
              appearance: 'auto',
            }}
            value={rules.multiplierType}
            onChange={(e) =>
              setRules((p) => ({
                ...p,
                multiplierType: e.target.value as ScoringRules['multiplierType'],
              }))
            }
            onFocus={(e) => (e.currentTarget.style.borderColor = 'var(--accent)')}
            onBlur={(e) => (e.currentTarget.style.borderColor = 'var(--border)')}
          >
            <option value="none">None</option>
            <option value="grid_squares">Grid Squares</option>
            <option value="dxcc">DXCC Entities</option>
          </select>
        </div>

        {/* Band bonus multipliers */}
        <div>
          <label style={labelStyle}>Band Bonus Multipliers</label>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(100px, 1fr))',
              gap: 8,
              marginTop: 4,
            }}
          >
            {BANDS.map((band) => (
              <div key={band}>
                <span
                  style={{
                    fontSize: 12,
                    fontWeight: 600,
                    color: 'var(--text-primary)',
                    marginBottom: 2,
                    display: 'block',
                  }}
                >
                  {band}
                </span>
                <input
                  type="number"
                  min={0}
                  step={0.5}
                  style={{ ...inputStyle, padding: '5px 8px', fontSize: 13 }}
                  value={rules.bandBonuses[band] ?? 1}
                  onChange={(e) => handleBandBonus(band, e.target.value)}
                  onFocus={(e) =>
                    (e.currentTarget.style.borderColor = 'var(--accent)')
                  }
                  onBlur={(e) =>
                    (e.currentTarget.style.borderColor = 'var(--border)')
                  }
                />
              </div>
            ))}
          </div>
        </div>

        {/* Save */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 4 }}>
          <button
            style={{
              ...btnStyle,
              opacity: saving ? 0.5 : 1,
            }}
            disabled={saving}
            onClick={handleSave}
            onMouseEnter={(e) =>
              (e.currentTarget.style.background = 'var(--accent)')
            }
            onMouseLeave={(e) =>
              (e.currentTarget.style.background = 'var(--ksu-purple)')
            }
          >
            {saving ? 'Saving...' : 'Save Rules'}
          </button>
          {saved && (
            <span style={{ fontSize: 13, color: 'var(--accent)', fontWeight: 600 }}>
              Saved
            </span>
          )}
        </div>
      </div>
    </div>
  );
};

export default ContestRules;
