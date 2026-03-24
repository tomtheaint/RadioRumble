export interface Qso {
  id: number;
  contestId: number;
  stationCallsign: string;
  call: string;
  band: string;
  mode: string;
  frequency?: number;
  rstSent?: string;
  rstRcvd?: string;
  gridsquare?: string;
  myGridsquare?: string;
  qsoDate?: string;
  timeOn?: string;
  isMultiplier: boolean;
  points: number;
  createdAt: string;
}
