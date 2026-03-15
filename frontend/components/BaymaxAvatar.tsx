// frontend/components/BaymaxAvatar.tsx
"use client";
import { useEffect, useCallback, useRef, useState } from "react";
import { useBaymax } from "./BaymaxContext";

// ─── Configurable content (edit for other projects) ───────────────────────
const PAGE_TIPS: Record<string, string> = {
  home: "Paste an Amazon URL to analyze a product directly.",
  preview: "I'm scanning products. This may take a moment.",
  confirm: "Select the right product and I'll dig into the reviews.",
  results: "Scroll down to see what customers really think.",
  "url-analysis": "I'm analyzing reviews and price history for you.",
};

const QUOTES = [
  "I am not fast. But I am thorough.",
  "On a scale of one to ten, how would you rate your pain?",
  "I will always be there for you.",
  "Hairy baby.",
  "Your health is my only concern.",
];

const HOVER_GREETINGS = [
  "Hello. I am Baymax.",
  "How can I help you today?",
  "I detected your cursor. Are you okay?",
  "Fist bump?",
];
// ──────────────────────────────────────────────────────────────────────────

function randomFrom(arr: string[]): string {
  return arr[Math.floor(Math.random() * arr.length)];
}

export function BaymaxAvatar() {
  const { message, say, dismiss, currentPage } = useBaymax();
  const dismissTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const hoverTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [hovered, setHovered] = useState(false);

  // Auto-dismiss after 4 seconds whenever message changes
  useEffect(() => {
    if (dismissTimer.current) clearTimeout(dismissTimer.current);
    if (message) {
      dismissTimer.current = setTimeout(() => dismiss(), 4000);
    }
    return () => {
      if (dismissTimer.current) clearTimeout(dismissTimer.current);
    };
  }, [message, dismiss]);

  // Show contextual tip 2s after page changes
  useEffect(() => {
    if (!currentPage) return;
    const tip = PAGE_TIPS[currentPage];
    if (!tip) return;
    const t = setTimeout(() => say(tip), 2000);
    return () => clearTimeout(t);
  }, [currentPage, say]);

  const handleClick = useCallback(() => {
    if (message) {
      dismiss();
    } else {
      say(randomFrom(QUOTES));
    }
  }, [message, dismiss, say]);

  const handleMouseEnter = useCallback(() => {
    setHovered(true);
    // Show a greeting after 800ms of hovering (don't interrupt existing message)
    hoverTimer.current = setTimeout(() => {
      if (!message) say(randomFrom(HOVER_GREETINGS));
    }, 800);
  }, [message, say]);

  const handleMouseLeave = useCallback(() => {
    setHovered(false);
    if (hoverTimer.current) clearTimeout(hoverTimer.current);
  }, []);

  return (
    <div style={{ position: "fixed", bottom: "2rem", right: "1.5rem", zIndex: 50 }} className="flex flex-col items-end gap-2">
      {/* Speech bubble */}
      {message && (
        <div
          onClick={dismiss}
          className="cursor-pointer max-w-[220px] rounded-[14px_14px_4px_14px] border border-indigo-600 bg-[#0e0e2a] px-3.5 py-2.5 text-[13px] leading-snug text-[#e0e0f0] shadow-xl"
          style={{ animation: "baymax-speech-in 0.25s ease-out forwards" }}
        >
          <span className="mb-1 block text-[10px] font-bold uppercase tracking-widest text-indigo-400">
            Baymax
          </span>
          {message}
        </div>
      )}

      {/* Avatar */}
      <button
        onClick={handleClick}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        aria-label="Baymax assistant"
        className="cursor-pointer border-0 p-0 bg-transparent"
        style={{ animation: "baymax-float-glow 3s ease-in-out infinite" }}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="/baymax.png"
          alt="Baymax"
          className="h-36 w-auto"
          style={{
            transform: hovered ? "scale(1.08)" : "scale(1)",
            filter: hovered
              ? "drop-shadow(0 0 18px rgba(165, 180, 252, 0.6))"
              : "none",
            transition: "transform 0.25s ease, filter 0.25s ease",
          }}
        />
      </button>
    </div>
  );
}
