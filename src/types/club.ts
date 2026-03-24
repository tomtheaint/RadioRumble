export interface Club {
  id: number;
  name: string;
  callsign?: string;
  contestId: number;
  createdAt: string;
  operators?: Operator[];
}

export interface Operator {
  id: number;
  callsign: string;
  clubId: number;
  contestId: number;
}
