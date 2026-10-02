"use client";

import { useEffect, useRef, useState } from "react";
import { wsBase } from "./api";
import type { IntersectionWsPayload } from "./types";

export type ConnectionStatus = "CONNECTING" | "CONNECTED" | "DISCONNECTED" | "STALE";
const STALE_AFTER_MS = 8000;

export function useIntersectionSocket(intersectionId: string | null) {
  const [payload, setPayload] = useState<IntersectionWsPayload | null>(null);
  const [status, setStatus] = useState<ConnectionStatus>("CONNECTING");
  const [lastUpdate, setLastUpdate] = useState<number | null>(null);
  const updateRef = useRef<number | null>(null);

  useEffect(() => {
    let disposed = false;
    let socket: WebSocket | null = null;
    let reconnect: ReturnType<typeof setTimeout> | undefined;
    let attempt = 0;
    updateRef.current = null;
    setPayload(null); setLastUpdate(null);
    setStatus(intersectionId ? "CONNECTING" : "DISCONNECTED");
    if (!intersectionId) return;

    const retry = () => {
      if (disposed) return;
      setStatus("DISCONNECTED");
      reconnect = setTimeout(connect, Math.min(1000 * 2 ** ++attempt, 15000));
    };
    const connect = () => {
      if (disposed) return;
      setStatus("CONNECTING");
      let current: WebSocket;
      try { current = new WebSocket(`${wsBase()}/ws/intersections/${intersectionId}`); }
      catch { retry(); return; }
      socket = current;
      current.onopen = () => { if (!disposed) { attempt = 0; setStatus("CONNECTED"); } };
      current.onmessage = event => {
        if (disposed || socket !== current) return;
        try {
          const data = JSON.parse(event.data) as IntersectionWsPayload;
          if (data.intersection_id !== intersectionId) return;
          const received = Date.now(); updateRef.current = received;
          setPayload(data); setLastUpdate(received); setStatus("CONNECTED");
        } catch { /* Ignore malformed frames; stale detection exposes missing updates. */ }
      };
      current.onclose = () => { if (!disposed && socket === current) retry(); };
      current.onerror = () => { /* onclose schedules reconnection. */ };
    };
    connect();
    const stale = setInterval(() => {
      if (socket?.readyState === WebSocket.OPEN && updateRef.current && Date.now() - updateRef.current > STALE_AFTER_MS) setStatus("STALE");
    }, 1000);
    return () => { disposed = true; clearTimeout(reconnect); clearInterval(stale); socket?.close(); };
  }, [intersectionId]);

  return { payload, status, lastUpdate };
}
