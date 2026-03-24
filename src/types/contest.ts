export interface Contest {
  id: number;
  name: string;
  description?: string;
  startTime?: string;
  endTime?: string;
  status: 'pending' | 'active' | 'completed';
  rules?: string;
  createdAt: string;
}
