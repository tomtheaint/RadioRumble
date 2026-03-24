import { useEffect, useRef } from 'react';
import { useWebSocketStore } from '../stores/useWebSocketStore';

const RECONNECT_DELAY = 3000;

export function useWebSocket(contestId: number | null) {
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const connected = useWebSocketStore((s) => s.connected);

  useEffect(() => {
    if (contestId === null) return;

    const { connect, disconnect } = useWebSocketStore.getState();
    connect(contestId);

    const unsubscribe = useWebSocketStore.subscribe((state, prev) => {
      if (prev.connected && !state.connected) {
        reconnectTimer.current = setTimeout(() => {
          useWebSocketStore.getState().connect(contestId);
        }, RECONNECT_DELAY);
      }
    });

    return () => {
      unsubscribe();
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current);
        reconnectTimer.current = null;
      }
      useWebSocketStore.getState().disconnect();
    };
  }, [contestId]);

  return { connected };
}
