import { Qso } from './qso';

export interface StationScore {
  callsign: string;
  clubName: string | null;
  totalQsos: number;
  totalPoints: number;
  bands: Record<string, number>;
  modes: Record<string, number>;
  rate: number;
}

export interface ClubTotal {
  clubName: string;
  totalQsos: number;
  totalPoints: number;
}

export type WsMessage =
  | {
      type: 'scoreboard';
      contestId: number;
      data: {
        stations: StationScore[];
        clubTotals: ClubTotal[];
        contestStatus: string;
        elapsed: number;
        remaining: number | null;
      };
    }
  | { type: 'qso'; contestId: number; data: Qso }
  | { type: 'contest_status'; contestId: number; status: string }
  | {
      type: 'rate_update';
      contestId: number;
      data: Array<{
        stationCallsign: string;
        rate: number;
        trend: 'up' | 'down' | 'flat';
      }>;
    };
