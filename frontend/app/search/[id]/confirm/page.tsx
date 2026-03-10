// frontend/app/search/[id]/confirm/page.tsx
"use client";
import { useEffect, useState, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { ConfirmationGrid } from "@/components/ConfirmationGrid";
import { ProgressFeed } from "@/components/ProgressFeed";
import { useSSE } from "@/lib/useSSE";
import { confirmProducts } from "@/lib/api";

export default function ConfirmPage() {
  const { id: searchId } = useParams<{ id: string }>();
  const router = useRouter();
  const { events } = useSSE(searchId);
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
    // Pipeline resumes; redirect happens via "complete" SSE event
  };

  const handleNextBatch = async () => {
    setIsWaiting(true);
    await confirmProducts(searchId, []); // empty = reject all, fetch next batch
  };

  if (needsMoreDetail) {
    return (
      <main className="max-w-lg mx-auto px-4 py-16 text-center space-y-4">
        <h2 className="text-xl font-semibold text-gray-900">Could not find a match</h2>
        <p className="text-gray-500">
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
      <a href="/" className="text-sm text-gray-500 hover:text-gray-700">
        ← Back
      </a>
      <ProgressFeed events={events} />
      {isWaiting ? (
        <div className="text-center py-16 text-gray-500">Working on it...</div>
      ) : currentBatch.length > 0 ? (
        <ConfirmationGrid
          products={currentBatch}
          iteration={iteration}
          maxIterations={maxIterations}
          onConfirm={handleConfirm}
          onNextBatch={handleNextBatch}
        />
      ) : (
        <div className="text-center py-16 text-gray-400">Searching Amazon...</div>
      )}
    </main>
  );
}
