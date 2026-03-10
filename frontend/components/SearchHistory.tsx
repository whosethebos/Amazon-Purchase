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
    return <p className="text-sm text-gray-400">No searches yet.</p>;

  return (
    <div className="space-y-2">
      {items.map((item) => (
        <div
          key={item.id}
          className="flex items-center gap-2 p-3 bg-white rounded-lg border border-gray-200"
        >
          <div className="flex-1 min-w-0">
            <p className="font-medium text-gray-900 text-sm truncate">
              &quot;{item.query}&quot;
            </p>
            <p className="text-xs text-gray-400">
              {item.product_count} products ·{" "}
              {new Date(item.created_at).toLocaleDateString()}
            </p>
          </div>
          {item.status === "done" && (
            <Link
              href={`/search/${item.id}/results`}
              className="flex items-center gap-1 text-xs text-orange-500 hover:underline flex-shrink-0"
            >
              View <ChevronRight size={12} />
            </Link>
          )}
          <button
            onClick={() => onDelete(item.id)}
            className="p-1.5 text-gray-400 hover:text-red-500 rounded flex-shrink-0"
            title="Delete search"
          >
            <Trash2 size={14} />
          </button>
        </div>
      ))}
    </div>
  );
}
