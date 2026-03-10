// frontend/components/WatchlistCard.tsx
import Image from "next/image";
import { Trash2, RefreshCw, ExternalLink, TrendingDown, TrendingUp, Minus } from "lucide-react";

type WatchlistItem = {
  id: string;
  product: {
    title: string;
    url: string;
    image_url: string | null;
  };
  current_price: number | null;
  previous_price: number | null;
  last_checked_at: string | null;
};

type Props = {
  item: WatchlistItem;
  onDelete: (id: string) => void;
  onRefresh: (id: string) => void;
};

export function WatchlistCard({ item, onDelete, onRefresh }: Props) {
  const { product, current_price, previous_price } = item;
  const priceDiff =
    current_price != null && previous_price != null
      ? current_price - previous_price
      : null;

  return (
    <div className="flex items-center gap-3 p-3 bg-white rounded-lg border border-gray-200">
      {product.image_url && (
        <div className="w-12 h-12 relative flex-shrink-0 rounded overflow-hidden bg-gray-100">
          <Image
            src={product.image_url}
            alt={product.title}
            fill
            className="object-contain"
            unoptimized
          />
        </div>
      )}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-900 line-clamp-1">{product.title}</p>
        <div className="flex items-center gap-2 text-sm">
          {current_price != null && (
            <span className="font-bold text-gray-800">${current_price}</span>
          )}
          {priceDiff != null && priceDiff !== 0 && (
            <span
              className={`flex items-center gap-0.5 text-xs ${
                priceDiff < 0 ? "text-green-600" : "text-red-500"
              }`}
            >
              {priceDiff < 0 ? <TrendingDown size={12} /> : <TrendingUp size={12} />}
              {priceDiff < 0
                ? `-$${Math.abs(priceDiff).toFixed(2)}`
                : `+$${priceDiff.toFixed(2)}`}
            </span>
          )}
          {priceDiff === 0 && <Minus size={12} className="text-gray-400" />}
        </div>
      </div>
      <div className="flex gap-1">
        <a
          href={product.url}
          target="_blank"
          rel="noopener noreferrer"
          className="p-1.5 text-gray-400 hover:text-orange-500 rounded"
        >
          <ExternalLink size={14} />
        </a>
        <button
          onClick={() => onRefresh(item.id)}
          className="p-1.5 text-gray-400 hover:text-blue-500 rounded"
          title="Refresh price"
        >
          <RefreshCw size={14} />
        </button>
        <button
          onClick={() => onDelete(item.id)}
          className="p-1.5 text-gray-400 hover:text-red-500 rounded"
          title="Remove from watchlist"
        >
          <Trash2 size={14} />
        </button>
      </div>
    </div>
  );
}
