import { useEffect } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Header from './components/Layout/Header';
import Nav from './components/Layout/Nav';
import Scoreboard from './components/Scoreboard/Scoreboard';
import MapPage from './components/Map/MapPage';
import StatsDashboard from './components/Stats/StatsDashboard';
import ContestManager from './components/Contest/ContestManager';
import { useWebSocket } from './hooks/useWebSocket';
import { useContestStore } from './stores/useContestStore';

export default function App() {
  const activeContest = useContestStore((s) => s.activeContest);
  useWebSocket(activeContest?.id ?? null);

  useEffect(() => {
    useContestStore.getState().fetchContests();
  }, []);

  return (
    <BrowserRouter>
      <div
        className="app-shell"
        style={{
          display: 'flex',
          flexDirection: 'column',
          height: '100vh',
          overflow: 'hidden',
        }}
      >
        <Header />
        <Nav />
        <main className="main-content" style={{ flex: 1, overflowY: 'auto' }}>
          <Routes>
            <Route path="/" element={<Scoreboard />} />
            <Route path="/map" element={<MapPage />} />
            <Route path="/stats" element={<StatsDashboard />} />
            <Route path="/manage" element={<ContestManager />} />
          </Routes>
        </main>
      </div>

      <style>{`
        @media (max-width: 768px) {
          .app-shell {
            height: 100vh !important;
            height: 100dvh !important;
          }
          .main-content {
            padding-bottom: 56px !important;
          }
        }
      `}</style>
    </BrowserRouter>
  );
}
