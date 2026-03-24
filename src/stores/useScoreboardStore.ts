import { create } from 'zustand';
import { StationScore, ClubTotal } from '../types/ws';
import { Qso } from '../types/qso';

interface ScoreboardState {
  stations: StationScore[];
  clubTotals: ClubTotal[];

  updateFromSnapshot: (data: {
    stations: StationScore[];
    clubTotals: ClubTotal[];
  }) => void;
  updateFromQso: (qso: Qso) => void;
}

export const useScoreboardStore = create<ScoreboardState>((set) => ({
  stations: [],
  clubTotals: [],

  updateFromSnapshot: (data) =>
    set({ stations: data.stations, clubTotals: data.clubTotals }),

  updateFromQso: (qso) =>
    set((state) => {
      const stations = state.stations.map((s) => {
        if (s.callsign !== qso.stationCallsign) return s;
        return {
          ...s,
          totalQsos: s.totalQsos + 1,
          totalPoints: s.totalPoints + qso.points,
          bands: {
            ...s.bands,
            [qso.band]: (s.bands[qso.band] || 0) + 1,
          },
          modes: {
            ...s.modes,
            [qso.mode]: (s.modes[qso.mode] || 0) + 1,
          },
        };
      });

      const clubMap = new Map<string, ClubTotal>();
      for (const station of stations) {
        if (!station.clubName) continue;
        const existing = clubMap.get(station.clubName);
        clubMap.set(station.clubName, {
          clubName: station.clubName,
          totalQsos: (existing?.totalQsos ?? 0) + station.totalQsos,
          totalPoints: (existing?.totalPoints ?? 0) + station.totalPoints,
        });
      }

      return { stations, clubTotals: Array.from(clubMap.values()) };
    }),
}));
