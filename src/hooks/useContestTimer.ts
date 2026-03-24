import { useEffect } from 'react';
import { useContestStore } from '../stores/useContestStore';

export function useContestTimer() {
  const activeContest = useContestStore((s) => s.activeContest);
  const setElapsed = useContestStore((s) => s.setElapsed);
  const setRemaining = useContestStore((s) => s.setRemaining);

  useEffect(() => {
    if (!activeContest?.startTime) return;

    const startMs = new Date(activeContest.startTime).getTime();
    const endMs = activeContest.endTime
      ? new Date(activeContest.endTime).getTime()
      : null;

    const tick = () => {
      const now = Date.now();
      const elapsedSec = Math.max(0, Math.floor((now - startMs) / 1000));
      setElapsed(elapsedSec);

      if (endMs !== null) {
        const remainSec = Math.max(0, Math.floor((endMs - now) / 1000));
        setRemaining(remainSec);
      } else {
        setRemaining(null);
      }
    };

    tick();
    const interval = setInterval(tick, 1000);

    return () => clearInterval(interval);
  }, [activeContest?.startTime, activeContest?.endTime, setElapsed, setRemaining]);
}
