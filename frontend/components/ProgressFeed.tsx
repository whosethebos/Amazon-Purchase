// frontend/components/ProgressFeed.tsx
"use client";
import { useEffect, useRef } from "react";
import type { SSEEvent } from "@/lib/useSSE";

type Props = { events: SSEEvent[] };

function eventStyle(event: string): { icon: string; color: string } {
  if (event === "complete")       return { icon: "✓", color: "text-emerald-400" };
  if (event === "analysis_done")  return { icon: "✓", color: "text-emerald-500" };
  if (event === "batch_ready")    return { icon: "◆", color: "text-orange-400" };
  if (event === "error")          return { icon: "✕", color: "text-red-400" };
  return { icon: "›", color: "text-[#818cf8]" };
}

export function ProgressFeed({ events }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events]);

  if (events.length === 0) return null;

  return (
    <div className="bg-[#08080f] border border-[#1e1e30] rounded-lg p-4 space-y-1.5 max-h-44 overflow-y-auto font-mono">
      {events.map((e, i) => {
        const { icon, color } = eventStyle(e.event);
        const msg = String((e.data as { message?: string }).message ?? e.event);
        const isLatest = i === events.length - 1;
        return (
          <div key={i} className={`text-xs flex items-start gap-2 ${isLatest ? "text-[#c8c8e0]" : "text-[#4a4a6a]"}`}>
            <span className={`${color} shrink-0 mt-px`}>{icon}</span>
            <span className="flex-1">{msg}</span>
            {isLatest && (
              <span className="shrink-0 mt-1.5 w-1.5 h-1.5 rounded-full bg-indigo-400 animate-pulse" />
            )}
          </div>
        );
      })}
      <div ref={bottomRef} />
    </div>
  );
}
