// frontend/components/SearchHistory.tsx
import { Trash2, ChevronRight } from "lucide-react";
import Link from "next/link";

type HistoryItem = {
  id: string;
  query: string;
  status: string;
  product_count: number;
  created_at: string;
};

type Props = {
  items: HistoryItem[];
  onDelete: (id: string) => void;
};

export function SearchHistory({ items, onDelete }: Props) {
  if (items.length === 0)
    return <p className="text-sm text-[#4a4a6a]">No searches yet.</p>;

  return (
    <div className="space-y-2">
      {items.map((item) => (
        <div
          key={item.id}
          className="flex items-center gap-2 p-3 bg-[#141418] rounded-lg border border-[#252530] hover:border-[#353548] transition-colors"
        >
          <div className="flex-1 min-w-0">
            <p className="font-medium text-[#ebebf5] text-sm truncate">
              &quot;{item.query}&quot;
            </p>
            <p className="text-xs text-[#4a4a6a] font-mono">
              {item.product_count} products ·{" "}
              {new Date(item.created_at).toLocaleDateString()}
            </p>
          </div>
          {item.status === "done" && (
            <Link
              href={`/search/${item.id}/results`}
              className="flex items-center gap-1 text-xs text-orange-400 hover:text-orange-300 transition-colors flex-shrink-0"
            >
              View <ChevronRight size={12} />
            </Link>
          )}
          <button
            onClick={() => onDelete(item.id)}
            className="p-1.5 text-[#4a4a6a] hover:text-red-400 rounded transition-colors flex-shrink-0"
            title="Delete search"
          >
            <Trash2 size={14} />
          </button>
        </div>
      ))}
    </div>
  );
}
