// frontend/components/ProgressFeed.tsx
import type { SSEEvent } from "@/lib/useSSE";

type Props = { events: SSEEvent[] };

export function ProgressFeed({ events }: Props) {
  if (events.length === 0) return null;
  return (
    <div className="bg-gray-50 rounded-lg p-4 space-y-1 max-h-40 overflow-y-auto">
      {events.map((e, i) => (
        <div key={i} className="text-sm text-gray-600 flex items-center gap-2">
          <span className="text-orange-400">›</span>
          {String((e.data as { message?: string }).message ?? e.event)}
        </div>
      ))}
    </div>
  );
}
