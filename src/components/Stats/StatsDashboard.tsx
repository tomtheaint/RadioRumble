import { useEffect, useState } from 'react';
import { useContestStore } from '../../stores/useContestStore';
import RateChart from './RateChart';
import BandChart from './BandChart';
import ModeChart from './ModeChart';
import MultiplierTracker from './MultiplierTracker';

interface RateData {
  hour: string;
  count: number;
}

interface StatsResponse {
  rate: RateData[];
  bands: Record<string, number>;
  modes: Record<string, number>;
  grids: string[];
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={styles.card}>
      <div style={styles.cardTitle}>{title}</div>
      <div style={styles.cardBody}>{children}</div>
    </div>
  );
}

export default function StatsDashboard() {
  const activeContest = useContestStore((s) => s.activeContest);
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!activeContest) return;

    const fetchAll = async () => {
      setLoading(true);
      try {
        const id = activeContest.id;
        const [rateRes, bandsRes, modesRes, statsRes] = await Promise.all([
          fetch(`/api/contests/${id}/stats/rate`),
          fetch(`/api/contests/${id}/stats/bands`),
          fetch(`/api/contests/${id}/stats/modes`),
          fetch(`/api/contests/${id}/stats`),
        ]);

        const rate: RateData[] = rateRes.ok ? await rateRes.json() : [];
        const bandsArr = bandsRes.ok ? await bandsRes.json() : [];
        const bands: Record<string, number> = {};
        for (const b of bandsArr) bands[b.band] = b.count;
        const modesArr = modesRes.ok ? await modesRes.json() : [];
        const modes: Record<string, number> = {};
        for (const m of modesArr) modes[m.mode] = m.count;
        const statsData = statsRes.ok ? await statsRes.json() : { grids: [] };

        setStats({
          rate,
          bands,
          modes,
          grids: statsData.grids || [],
        });
      } catch {
        // silently fail
      } finally {
        setLoading(false);
      }
    };

    fetchAll();
  }, [activeContest]);

  if (!activeContest) {
    return (
      <div style={styles.container}>
        <div style={styles.empty}>Select a contest to view statistics.</div>
      </div>
    );
  }

  if (loading) {
    return (
      <div style={styles.container}>
        <div style={styles.empty}>Loading statistics...</div>
      </div>
    );
  }

  return (
    <div style={styles.container}>
      <div className="stats-grid-mobile" style={styles.grid}>
        <Card title="QSOs Over Time">
          <RateChart data={stats?.rate || []} />
        </Card>
        <Card title="Band Distribution">
          <BandChart data={stats?.bands || {}} />
        </Card>
        <Card title="Mode Distribution">
          <ModeChart data={stats?.modes || {}} />
        </Card>
        <Card title="Multipliers (Unique Grids)">
          <MultiplierTracker grids={stats?.grids || []} />
        </Card>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    padding: 24,
    height: '100%',
    boxSizing: 'border-box',
    overflow: 'auto',
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: 20,
    maxWidth: 1200,
    margin: '0 auto',
  },
  card: {
    background: '#2d1d42',
    borderRadius: 12,
    padding: 20,
    border: '1px solid rgba(81, 40, 136, 0.3)',
  },
  cardTitle: {
    color: '#F4C55C',
    fontSize: 15,
    fontWeight: 600,
    marginBottom: 16,
    textTransform: 'uppercase' as const,
    letterSpacing: '0.5px',
  },
  cardBody: {
    color: '#E7DED0',
  },
  empty: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    height: '100%',
    color: '#E7DED0',
    fontSize: 16,
  },
};

// Mobile style injection
if (typeof document !== 'undefined') {
  const styleId = 'stats-mobile-styles';
  if (!document.getElementById(styleId)) {
    const style = document.createElement('style');
    style.id = styleId;
    style.textContent = `
      @media (max-width: 768px) {
        .stats-grid-mobile {
          grid-template-columns: 1fr !important;
          gap: 14px !important;
        }
      }
    `;
    document.head.appendChild(style);
  }
}
