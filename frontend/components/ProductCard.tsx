// frontend/components/ProductCard.tsx
import Image from "next/image";
import { ExternalLink, Plus } from "lucide-react";

type Analysis = {
  summary: string;
  pros: string[];
  cons: string[];
  score: number;
  rank: number;
};

type Product = {
  id: string;
  title: string;
  price: number | null;
  rating: number | null;
  review_count: number | null;
  url: string;
  image_url: string | null;
  analysis?: Analysis | null;
};

type Props = {
  product: Product;
  onAddToWatchlist?: (productId: string) => void;
};

export function ProductCard({ product, onAddToWatchlist }: Props) {
  const { analysis } = product;
  const asin = product.url.match(/\/dp\/([A-Z0-9]{10})/)?.[1];
  const keepaMarketplace =
    product.url.includes("amazon.in")     ? 10 :
    product.url.includes("amazon.co.uk")  ? 2  :
    product.url.includes("amazon.de")     ? 3  :
    product.url.includes("amazon.fr")     ? 4  :
    product.url.includes("amazon.ca")     ? 6  :
    product.url.includes("amazon.it")     ? 8  :
    product.url.includes("amazon.es")     ? 9  :
    product.url.includes("amazon.com.au") ? 12 : 1;
    // amazon.com.au MUST stay last — "amazon.com" is a substring of
    // "amazon.com.au". Do NOT add an explicit amazon.com check above it.
  const priceHistoryUrl = asin
    ? `https://keepa.com/#!product/${keepaMarketplace}-${asin}`
    : undefined;

  return (
    <div className="bg-[#141418] rounded-xl border border-[#252530] p-5 flex gap-4 hover:border-[#353548] transition-colors">
      {/* Rank badge */}
      {analysis?.rank && (
        <div className="flex-shrink-0 w-10 h-10 bg-orange-500 text-white rounded-full flex items-center justify-center font-bold text-lg self-start mt-1 font-mono">
          {analysis.rank}
        </div>
      )}

      {/* Image */}
      {product.image_url && (
        <div className="flex-shrink-0 w-24 h-24 relative rounded-lg overflow-hidden bg-[#1c1c22]">
          <Image
            src={product.image_url}
            alt={product.title}
            fill
            className="object-contain p-1"
            unoptimized
          />
        </div>
      )}

      {/* Content */}
      <div className="flex-1 min-w-0 space-y-2">
        <div className="flex items-start justify-between gap-2">
          <h3 className="font-semibold text-[#ebebf5] line-clamp-2">{product.title}</h3>
          {analysis?.score != null && (
            <span className="flex-shrink-0 text-sm font-bold text-orange-400 bg-orange-500/10 px-2 py-0.5 rounded-full font-mono">
              {analysis.score}/100
            </span>
          )}
        </div>

        <div className="flex items-center gap-3 text-sm text-[#7878a0]">
          {product.price && (
            <span className="text-lg font-bold text-[#ebebf5] font-mono">${product.price}</span>
          )}
          {product.rating && <span className="text-amber-400">★ {product.rating}</span>}
          {product.review_count && (
            <span>({product.review_count.toLocaleString()} reviews)</span>
          )}
        </div>

        {analysis && (
          <div className="space-y-1">
            <p className="text-sm text-[#9898b8]">{analysis.summary}</p>
            <div className="flex flex-wrap gap-x-4 text-xs">
              {analysis.pros.length > 0 && (
                <div>
                  <span className="text-emerald-400 font-semibold">Pros: </span>
                  <span className="text-[#7878a0]">{analysis.pros.slice(0, 2).join(" · ")}</span>
                </div>
              )}
              {analysis.cons.length > 0 && (
                <div>
                  <span className="text-red-400 font-semibold">Cons: </span>
                  <span className="text-[#7878a0]">{analysis.cons.slice(0, 2).join(" · ")}</span>
                </div>
              )}
            </div>
          </div>
        )}

        <div className="flex gap-3 pt-1">
          {/* Clicking opens Amazon URL in a new tab */}
          <a
            href={product.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 text-sm text-orange-400 hover:text-orange-300 transition-colors"
          >
            <ExternalLink size={14} /> View on Amazon
          </a>
          {priceHistoryUrl && (
            <a
              href={priceHistoryUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 text-sm text-orange-400 hover:text-orange-300 transition-colors"
            >
              ↗ price history
            </a>
          )}
          {onAddToWatchlist && (
            <button
              onClick={() => onAddToWatchlist(product.id)}
              className="flex items-center gap-1 text-sm text-[#7878a0] hover:text-[#ebebf5] transition-colors"
            >
              <Plus size={14} /> Watchlist
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
