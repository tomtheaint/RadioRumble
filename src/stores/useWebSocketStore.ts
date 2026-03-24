import { create } from 'zustand';
import { WsMessage } from '../types/ws';
import { useScoreboardStore } from './useScoreboardStore';
import { useQsoStore } from './useQsoStore';
import { useContestStore } from './useContestStore';

interface WebSocketState {
  connected: boolean;
  ws: WebSocket | null;

  connect: (contestId: number) => void;
  disconnect: () => void;
}

function handleMessage(msg: WsMessage) {
  switch (msg.type) {
    case 'scoreboard':
      useScoreboardStore.getState().updateFromSnapshot(msg.data);
      useContestStore.getState().updateStatus(msg.data.contestStatus as 'pending' | 'active' | 'completed');
      useContestStore.getState().setElapsed(msg.data.elapsed);
      useContestStore.getState().setRemaining(msg.data.remaining);
      break;
    case 'qso':
      useQsoStore.getState().addQso(msg.data);
      useScoreboardStore.getState().updateFromQso(msg.data);
      break;
    case 'contest_status':
      useContestStore.getState().updateStatus(msg.status as 'pending' | 'active' | 'completed');
      break;
    case 'rate_update':
      useScoreboardStore.setState((state) => ({
        stations: state.stations.map((s) => {
          const update = msg.data.find((u) => u.stationCallsign === s.callsign);
          return update ? { ...s, rate: update.rate } : s;
        }),
      }));
      break;
  }
}

export const useWebSocketStore = create<WebSocketState>((set, get) => ({
  connected: false,
  ws: null,

  connect: (contestId) => {
    const existing = get().ws;
    if (existing) {
      existing.close();
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${protocol}//${window.location.host}/ws/contest/${contestId}`;
    const ws = new WebSocket(url);

    ws.onopen = () => set({ connected: true });

    ws.onclose = () => set({ connected: false, ws: null });

    ws.onerror = () => ws.close();

    ws.onmessage = (event) => {
      try {
        const msg: WsMessage = JSON.parse(event.data);
        handleMessage(msg);
      } catch {
        // ignore malformed messages
      }
    };

    set({ ws });
  },

  disconnect: () => {
    const ws = get().ws;
    if (ws) {
      ws.close();
    }
    set({ connected: false, ws: null });
  },
}));
