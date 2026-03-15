// frontend/components/BaymaxContext.tsx
"use client";
import { createContext, useContext, useState, useCallback, ReactNode } from "react";

export type BaymaxMood = "idle" | "happy" | "thinking" | "excited";

interface BaymaxContextValue {
  message: string | null;
  mood: BaymaxMood;
  say: (message: string) => void;
  dismiss: () => void;
  setPage: (page: string) => void;
  setMood: (mood: BaymaxMood) => void;
  currentPage: string | null;
}

const BaymaxContext = createContext<BaymaxContextValue | null>(null);

export function BaymaxProvider({ children }: { children: ReactNode }) {
  const [message, setMessage] = useState<string | null>(null);
  const [mood, setMoodState] = useState<BaymaxMood>("idle");
  const [currentPage, setCurrentPage] = useState<string | null>(null);

  const say = useCallback((msg: string) => {
    setMessage(msg);
  }, []);

  const dismiss = useCallback(() => {
    setMessage(null);
  }, []);

  const setPage = useCallback((page: string) => {
    setCurrentPage(page);
  }, []);

  const setMood = useCallback((mood: BaymaxMood) => {
    setMoodState(mood);
  }, []);

  return (
    <BaymaxContext.Provider value={{ message, mood, say, dismiss, setPage, setMood, currentPage }}>
      {children}
    </BaymaxContext.Provider>
  );
}

export function useBaymax() {
  const ctx = useContext(BaymaxContext);
  if (!ctx) throw new Error("useBaymax must be used within BaymaxProvider");
  return ctx;
}
