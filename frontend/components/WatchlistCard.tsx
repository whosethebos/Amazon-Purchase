// frontend/components/WatchlistCard.tsx
"use client";
import { useState } from "react";
import Image from "next/image";

type WatchlistItem = {
  id: string;
  product: {
    title: string;
    url: string;
    asin: string | null;
    currency: string | null;
    image_url: string | null;
  };
  current_price: number | null;
  previous_price: number | null;
  last_checked_at: string | null;
};

type Props = {
  item: WatchlistItem;
  onDelete: (id: string) => void;
  onRefresh: (id: string) => Promise<void>;
  isRefreshingAll?: boolean;
};

function formatLastChecked(ts: string | null): string {
  if (!ts) return "Never checked";
  const d = Date.now() - new Date(ts).getTime();
  if (d < 60_000) return "Just now";
  if (d < 3_600_000) return `Updated ${Math.floor(d / 60_000)}m ago`;
  if (d < 86_400_000) return `Updated ${Math.floor(d / 3_600_000)}h ago`;
  if (d < 172_800_000) return "Updated 1 day ago";
  return `Updated ${Math.floor(d / 86_400_000)} days ago`;
}

export function WatchlistCard({ item, onDelete, onRefresh, isRefreshingAll }: Props) {
  const [isRefreshing, setIsRefreshing] = useState(false);
  const { product, current_price, previous_price, last_checked_at } = item;

  const priceDiff =
    current_price != null && previous_price != null
      ? current_price - previous_price
      : null;

  const asin = product.asin || product.url.match(/\/dp\/([A-Z0-9]{10})/)?.[1];
  const keepaMarketplace =
    product.url.includes("amazon.in") ? 10 :
    product.url.includes("amazon.co.uk") ? 2 :
    product.url.includes("amazon.de") ? 3 :
    product.url.includes("amazon.fr") ? 4 :
    product.url.includes("amazon.ca") ? 6 :
    product.url.includes("amazon.it") ? 8 :
    product.url.includes("amazon.es") ? 9 :
    product.url.includes("amazon.com.au") ? 12 : 1;
  const priceHistoryUrl = asin ? `https://keepa.com/#!product/${keepaMarketplace}-${asin}` : undefined;

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await onRefresh(item.id);
    setIsRefreshing(false);
  };

  const refreshBusy = isRefreshing || !!isRefreshingAll;

  return (
    <div
      className="border border-[#1f1f38] rounded-[14px] hover:border-[#2e2e55] transition-colors"
      style={{ background: "linear-gradient(135deg, #0f0f1a, #131325)" }}
    >
      <div className="flex items-center gap-3.5 p-3.5">
        {/* Image */}
        {product.image_url && (
          <div className="w-[60px] h-[60px] relative flex-shrink-0 rounded-xl overflow-hidden bg-[#0a0a14] border border-[#1a1a30]">
            <Image
              src={product.image_url}
              alt={product.title}
              fill
              className="object-contain"
              unoptimized
            />
          </div>
        )}

        {/* Body */}
        <div className="flex-1 min-w-0">
          <p className="text-[13px] font-semibold text-[#e0e0ff] line-clamp-1 mb-1.5">
            {product.title}
          </p>

          {/* Price row */}
          <div className="flex items-center gap-2">
            <span className="text-[18px] font-bold text-white tabular-nums">
              {current_price != null ? `${product.currency ?? "USD"} ${current_price.toFixed(2)}` : "—"}
            </span>
            {priceDiff != null && priceDiff !== 0 && (
              <span
                className={`text-[10px] font-bold rounded-md px-1.5 py-0.5 border ${
                  priceDiff < 0
                    ? "bg-[#052e16] text-[#4ade80] border-[#14532d]"
                    : "bg-[#2d0505] text-[#f87171] border-[#450a0a]"
                }`}
              >
                {priceDiff < 0
                  ? `↓ $${Math.abs(priceDiff).toFixed(2)} lower`
                  : `↑ $${priceDiff.toFixed(2)} higher`}
              </span>
            )}
          </div>

          {/* Meta row */}
          <div className="flex items-center gap-3 mt-1">
            {priceHistoryUrl && (
              <a
                href={priceHistoryUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-[10px] text-[#f97316] hover:text-[#fb923c]"
              >
                ↗ price history
              </a>
            )}
            <span className="text-[10px] text-[#2e2e50]">
              {formatLastChecked(last_checked_at)}
            </span>
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex flex-col gap-1.5 flex-shrink-0">
          {/* Refresh */}
          <button
            onClick={handleRefresh}
            disabled={refreshBusy}
            title="Refresh price"
            className="w-8 h-8 rounded-lg bg-[#0f0f1a] border border-[#1f1f38] flex items-center justify-center text-[#3a3a60] hover:text-sky-400 hover:border-[#1e3a5f] transition-colors disabled:opacity-40"
          >
            <span className={refreshBusy ? "animate-spin inline-block" : ""}>↻</span>
          </button>

          {/* Open on Amazon */}
          <a
            href={product.url}
            target="_blank"
            rel="noopener noreferrer"
            className="w-8 h-8 rounded-lg bg-[#0f0f1a] border border-[#1f1f38] flex items-center justify-center text-[#3a3a60] hover:text-orange-400 transition-colors"
            title="Open on Amazon"
          >
            ↗
          </a>

          {/* Remove */}
          <button
            onClick={() => onDelete(item.id)}
            title="Remove from watchlist"
            className="w-8 h-8 rounded-lg bg-[#0f0f1a] border border-[#1f1f38] flex items-center justify-center text-[#3a3a60] hover:text-red-400 hover:border-[#7f1d1d] transition-colors"
          >
            ✕
          </button>
        </div>
      </div>
    </div>
  );
}
