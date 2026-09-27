"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { wsBase } from "./api";
import type { IntersectionWsPayload } from "./types";

export type ConnectionStatus = "CONNECTING" | "CONNECTED" | "DISCONNECTED" | "STALE";

const STALE_AFTER_MS = 8000;
const MAX_BACKOFF_MS = 15000;

export function useIntersectionSocket(intersectionId: string | null) {
  const [payload, setPayload] = useState<IntersectionWsPayload | null>(null);
  const [status, setStatus] = useState<ConnectionStatus>("CONNECTING");
  const [lastUpdate, setLastUpdate] = useState<number | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const attemptRef = useRef(0);
  const closedByUsRef = useRef(false);

  const connect = useCallback(() => {
    if (!intersectionId) return;
    closedByUsRef.current = false;
    setStatus("CONNECTING");

    let ws: WebSocket;
    try {
      ws = new WebSocket(`${wsBase()}/ws/intersections/${intersectionId}`);
    } catch {
      setStatus("DISCONNECTED");
      scheduleReconnect();
      return;
    }
    wsRef.current = ws;

    ws.onopen = () => {
      attemptRef.current = 0;
      setStatus("CONNECTED");
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as IntersectionWsPayload;
        setPayload(data);
        setLastUpdate(Date.now());
        setStatus("CONNECTED");
      } catch {
        // Malformed message - ignore this frame rather than crashing the dashboard.
      }
    };

    ws.onerror = () => {
      // onclose fires next and drives reconnect logic.
    };

    ws.onclose = () => {
      if (closedByUsRef.current) return;
      setStatus("DISCONNECTED");
      scheduleReconnect();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [intersectionId]);

  const scheduleReconnect = useCallback(() => {
    attemptRef.current += 1;
    const delay = Math.min(1000 * 2 ** attemptRef.current, MAX_BACKOFF_MS);
    setTimeout(() => {
      connect();
    }, delay);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connect]);

  useEffect(() => {
    if (!intersectionId) return;
    connect();
    return () => {
      closedByUsRef.current = true;
      wsRef.current?.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [intersectionId]);

  // Stale-data detection: if connected but no message for STALE_AFTER_MS,
  // surface STALE rather than silently showing an old snapshot as current.
  useEffect(() => {
    const interval = setInterval(() => {
      if (status === "CONNECTED" && lastUpdate && Date.now() - lastUpdate > STALE_AFTER_MS) {
        setStatus("STALE");
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [status, lastUpdate]);

  return { payload, status, lastUpdate };
}
