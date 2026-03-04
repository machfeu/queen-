/**
 * useEvents.ts — Hook WebSocket unique pour les événements temps réel.
 * Se reconnecte automatiquement. Expose les 50 derniers événements.
 */

import { createContext, useContext, useEffect, useRef, useState, useCallback } from "react";
import type { ReactNode } from "react";
import React from "react";

export interface WsEvent {
  type: string;
  data: Record<string, unknown>;
  timestamp: number;
}

interface EventsCtx {
  events: WsEvent[];
  connected: boolean;
}

const Ctx = createContext<EventsCtx>({ events: [], connected: false });

const MAX_EVENTS = 50;
const RECONNECT_MS = 3_000;

export function EventsProvider({ children }: { children: ReactNode }) {
  const [events, setEvents] = useState<WsEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectRef = useRef<ReturnType<typeof setTimeout>>();

  const connect = useCallback(() => {
    try {
      const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
      const url = `${proto}//${window.location.host}/ws/events`;
      const ws = new WebSocket(url);

      ws.onopen = () => setConnected(true);

      ws.onmessage = (msg) => {
        try {
          const evt: WsEvent = JSON.parse(msg.data);
          setEvents((prev) => [evt, ...prev].slice(0, MAX_EVENTS));
        } catch { /* ignore malformed */ }
      };

      ws.onclose = () => {
        setConnected(false);
        reconnectRef.current = setTimeout(connect, RECONNECT_MS);
      };

      ws.onerror = () => ws.close();

      wsRef.current = ws;
    } catch {
      reconnectRef.current = setTimeout(connect, RECONNECT_MS);
    }
  }, []);

  useEffect(() => {
    connect();
    return () => {
      wsRef.current?.close();
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
    };
  }, [connect]);

  return React.createElement(Ctx.Provider, { value: { events, connected } }, children);
}

export function useEvents() {
  return useContext(Ctx);
}
