// frontend/app/search/[id]/confirm/page.tsx
"use client";
import { useEffect, useState, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { ConfirmationGrid } from "@/components/ConfirmationGrid";
import { ProgressFeed } from "@/components/ProgressFeed";
import { StepIndicator } from "@/components/StepIndicator";
import { useSSE } from "@/lib/useSSE";
import { confirmProducts } from "@/lib/api";
import type { SSEEvent } from "@/lib/useSSE";
import { useBaymax } from "@/components/BaymaxContext";

// ── Workflow status panel ────────────────────────────────────────────────────

type Phase = "scraping" | "analyzing" | "ranking" | "done";

const PHASE_ORDER: Phase[] = ["scraping", "analyzing", "ranking", "done"];

const PHASE_LABELS: Record<Phase, string> = {
  scraping:  "Scraping reviews",
  analyzing: "AI analysis",
  ranking:   "Ranking results",
  done:      "Complete",
};

function detectPhase(events: SSEEvent[]): Phase {
  for (let i = events.length - 1; i >= 0; i--) {
    const e = events[i];
    const status = (e.data as { status?: string }).status;
    if (e.event === "complete" || e.event === "analysis_done") return "done";
    if (status === "ranking")   return "ranking";
    if (status === "analyzing") return "analyzing";
    if (status === "scraping")  return "scraping";
  }
  return "scraping";
}

function WorkflowStatus({ events }: { events: SSEEvent[] }) {
  const phase = detectPhase(events);
  const phaseIdx = PHASE_ORDER.indexOf(phase);
  const latestMsg = events.length > 0
    ? String((events[events.length - 1].data as { message?: string }).message ?? "")
    : null;

  return (
    <div className="space-y-4 py-6">
      {/* Phase stepper */}
      <div className="flex items-center gap-1">
        {(["scraping", "analyzing", "ranking"] as Phase[]).map((p, i) => {
          const idx = PHASE_ORDER.indexOf(p);
          const isDone   = phaseIdx > idx;
          const isActive = phaseIdx === idx;
          return (
            <div key={p} className="flex items-center gap-1 flex-1 min-w-0">
              <div className={`flex items-center gap-1.5 shrink-0 ${
                isDone   ? "text-emerald-400" :
                isActive ? "text-orange-400"  :
                           "text-[#3a3a58]"
              }`}>
                {isDone ? (
                  <span className="text-sm">✓</span>
                ) : isActive ? (
                  <span className="inline-block w-3 h-3 rounded-full border-2 border-orange-400 border-t-transparent animate-spin" />
                ) : (
                  <span className="w-3 h-3 rounded-full border border-[#3a3a58] inline-block" />
                )}
                <span className={`text-xs font-medium whitespace-nowrap ${
                  isDone ? "text-emerald-400" : isActive ? "text-[#ebebf5]" : "text-[#3a3a58]"
                }`}>
                  {PHASE_LABELS[p]}
                </span>
              </div>
              {i < 2 && (
                <div className={`flex-1 h-px mx-1 ${phaseIdx > idx ? "bg-emerald-800" : "bg-[#1e1e30]"}`} />
              )}
            </div>
          );
        })}
      </div>

      {/* Latest message */}
      {latestMsg && (
        <p className="text-xs text-[#5a5a80] text-center truncate px-2">{latestMsg}</p>
      )}
    </div>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function ConfirmPage() {
  const { id: searchId } = useParams<{ id: string }>();
  const router = useRouter();
  const { events } = useSSE(searchId);
  const { setPage } = useBaymax();
  useEffect(() => { setPage("confirm"); }, [setPage]);
  const [currentBatch, setCurrentBatch] = useState<any[]>([]);
  const [iteration, setIteration] = useState(0);
  const [maxIterations, setMaxIterations] = useState(3);
  const [needsMoreDetail, setNeedsMoreDetail] = useState(false);
  const [isWaiting, setIsWaiting] = useState(false);
  const processedEvents = useRef(new Set<number>());

  useEffect(() => {
    events.forEach((event, idx) => {
      if (processedEvents.current.has(idx)) return;
      processedEvents.current.add(idx);

      // Keep Baymax speech bubble in sync with latest status
      if (event.event === "batch_ready") {
        const d = event.data as any;
        setCurrentBatch(d.batch ?? []);
        setIteration(d.iteration ?? 0);
        setMaxIterations(d.max_iterations ?? 3);
        setNeedsMoreDetail(d.needs_more_detail ?? false);
        setIsWaiting(false);
      }

      if (event.event === "complete") {
        router.push(`/search/${searchId}/results`);
      }
    });
  }, [events, router, searchId]);

  const handleConfirm = async (selectedIds: string[]) => {
    setIsWaiting(true);
    await confirmProducts(searchId, selectedIds);
  };

  const handleNextBatch = async () => {
    setIsWaiting(true);
    await confirmProducts(searchId, []);
  };

  if (needsMoreDetail) {
    return (
      <main className="max-w-lg mx-auto px-4 py-16 text-center space-y-4">
        <h2 className="text-xl font-semibold text-[#ebebf5]">Could not find a match</h2>
        <p className="text-[#7878a0]">
          After {iteration} attempts, we couldn&apos;t find the product you&apos;re looking for.
          Please try a more specific search query.
        </p>
        <a
          href="/"
          className="inline-block mt-4 px-5 py-2 bg-orange-500 text-white rounded-lg font-semibold hover:bg-orange-600"
        >
          ← Back to Search
        </a>
      </main>
    );
  }

  return (
    <main className="max-w-3xl mx-auto px-4 py-10 space-y-6">
      <a href="/" className="text-sm text-[#818cf8] hover:text-indigo-300">
        ← Back
      </a>
      <StepIndicator step={2} />
      <ProgressFeed events={events} />
      {isWaiting ? (
        <WorkflowStatus events={events} />
      ) : currentBatch.length > 0 ? (
        <ConfirmationGrid
          products={currentBatch}
          iteration={iteration}
          maxIterations={maxIterations}
          onConfirm={handleConfirm}
          onNextBatch={handleNextBatch}
        />
      ) : (
        <div className="text-center py-16 text-[#4a4a6a]">Searching Amazon...</div>
      )}
    </main>
  );
}
