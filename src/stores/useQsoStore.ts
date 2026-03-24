import { create } from 'zustand';
import { Qso } from '../types/qso';

const MAX_RECENT = 100;

interface QsoState {
  recentQsos: Qso[];

  addQso: (qso: Qso) => void;
  setQsos: (qsos: Qso[]) => void;
}

export const useQsoStore = create<QsoState>((set) => ({
  recentQsos: [],

  addQso: (qso) =>
    set((state) => ({
      recentQsos: [qso, ...state.recentQsos].slice(0, MAX_RECENT),
    })),

  setQsos: (qsos) => set({ recentQsos: qsos.slice(0, MAX_RECENT) }),
}));
