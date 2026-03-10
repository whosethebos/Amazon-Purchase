// frontend/lib/useSSE.ts
"use client";
import { useEffect, useRef, useState } from "react";
import { API_URL } from "./config";

export type SSEEvent = {
  event: string;
  data: Record<string, unknown>;
};

export function useSSE(searchId: string | null) {
  const [events, setEvents] = useState<SSEEvent[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isDone, setIsDone] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!searchId) return;

    const es = new EventSource(`${API_URL}/api/search/${searchId}/stream`);
    esRef.current = es;
    setIsConnected(true);

    es.onmessage = (e) => {
      const parsed: SSEEvent = JSON.parse(e.data);
      if (parsed.event === "done") {
        setIsDone(true);
        es.close();
        setIsConnected(false);
        return;
      }
      setEvents((prev) => [...prev, parsed]);
    };

    es.onerror = () => {
      es.close();
      setIsConnected(false);
    };

    return () => {
      es.close();
    };
  }, [searchId]);

  return { events, isConnected, isDone };
}
