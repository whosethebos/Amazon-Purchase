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

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 flex gap-4">
      {/* Rank badge */}
      {analysis?.rank && (
        <div className="flex-shrink-0 w-10 h-10 bg-orange-500 text-white rounded-full flex items-center justify-center font-bold text-lg self-start mt-1">
          {analysis.rank}
        </div>
      )}

      {/* Image */}
      {product.image_url && (
        <div className="flex-shrink-0 w-24 h-24 relative rounded-lg overflow-hidden bg-gray-100">
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
          <h3 className="font-semibold text-gray-900 line-clamp-2">{product.title}</h3>
          {analysis?.score != null && (
            <span className="flex-shrink-0 text-sm font-bold text-orange-600 bg-orange-50 px-2 py-0.5 rounded-full">
              {analysis.score}/100
            </span>
          )}
        </div>

        <div className="flex items-center gap-3 text-sm text-gray-500">
          {product.price && (
            <span className="text-lg font-bold text-gray-900">${product.price}</span>
          )}
          {product.rating && <span>★ {product.rating}</span>}
          {product.review_count && (
            <span>({product.review_count.toLocaleString()} reviews)</span>
          )}
        </div>

        {analysis && (
          <div className="space-y-1">
            <p className="text-sm text-gray-600">{analysis.summary}</p>
            <div className="flex flex-wrap gap-x-4 text-xs">
              {analysis.pros.length > 0 && (
                <div>
                  <span className="text-green-600 font-semibold">Pros: </span>
                  {analysis.pros.slice(0, 2).join(" · ")}
                </div>
              )}
              {analysis.cons.length > 0 && (
                <div>
                  <span className="text-red-500 font-semibold">Cons: </span>
                  {analysis.cons.slice(0, 2).join(" · ")}
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
            className="flex items-center gap-1 text-sm text-orange-500 hover:underline"
          >
            <ExternalLink size={14} /> View on Amazon
          </a>
          {onAddToWatchlist && (
            <button
              onClick={() => onAddToWatchlist(product.id)}
              className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
            >
              <Plus size={14} /> Watchlist
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
