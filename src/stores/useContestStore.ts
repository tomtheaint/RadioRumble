import { create } from 'zustand';
import { Contest } from '../types/contest';

interface ContestState {
  activeContest: Contest | null;
  contests: Contest[];
  elapsed: number;
  remaining: number | null;
  status: 'pending' | 'active' | 'completed';

  fetchContests: () => Promise<void>;
  createContest: (contest: Partial<Contest>) => Promise<void>;
  setActiveContest: (contest: Contest | null) => void;
  updateStatus: (status: 'pending' | 'active' | 'completed') => void;
  setElapsed: (elapsed: number) => void;
  setRemaining: (remaining: number | null) => void;
}

export const useContestStore = create<ContestState>((set) => ({
  activeContest: null,
  contests: [],
  elapsed: 0,
  remaining: null,
  status: 'pending',

  fetchContests: async () => {
    try {
      const res = await fetch('/api/contests');
      if (!res.ok) return;
      const contests: Contest[] = await res.json();
      const active = contests.find(c => c.status === 'active') || contests[0] || null;
      set({ contests, activeContest: active, status: active?.status || 'pending' });
    } catch {
      // API not available yet
    }
  },

  createContest: async (contest) => {
    const res = await fetch('/api/contests', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(contest),
    });
    const created: Contest = await res.json();
    set((state) => ({ contests: [...state.contests, created] }));
  },

  setActiveContest: (contest) => set({ activeContest: contest }),

  updateStatus: (status) => set({ status }),

  setElapsed: (elapsed) => set({ elapsed }),

  setRemaining: (remaining) => set({ remaining }),
}));
