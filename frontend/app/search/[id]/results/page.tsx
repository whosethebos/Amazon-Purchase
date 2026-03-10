// frontend/app/search/[id]/results/page.tsx
"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { ProductCard } from "@/components/ProductCard";
import { getResults, addToWatchlist } from "@/lib/api";

export default function ResultsPage() {
  const { id: searchId } = useParams<{ id: string }>();
  const [search, setSearch] = useState<any>(null);
  const [products, setProducts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [addedToWatchlist, setAddedToWatchlist] = useState<Set<string>>(new Set());

  useEffect(() => {
    getResults(searchId)
      .then(({ search, products }) => {
        setSearch(search);
        setProducts(products);
      })
      .finally(() => setLoading(false));
  }, [searchId]);

  const handleAddToWatchlist = async (productId: string) => {
    await addToWatchlist(productId);
    setAddedToWatchlist((prev) => new Set([...prev, productId]));
  };

  if (loading)
    return <div className="text-center py-16 text-gray-400">Loading results...</div>;

  return (
    <main className="max-w-3xl mx-auto px-4 py-10 space-y-6">
      <div className="flex items-center gap-3 flex-wrap">
        <a href="/" className="text-sm text-gray-500 hover:text-gray-700">
          ← Back
        </a>
        <h1 className="text-xl font-bold text-gray-900">
          Results: &quot;{search?.query}&quot;
        </h1>
        <span className="text-sm text-gray-400">{products.length} products</span>
      </div>

      {products.length === 0 ? (
        <p className="text-center text-gray-400 py-16">No results found.</p>
      ) : (
        <div className="space-y-4">
          {products.map((product) => (
            <ProductCard
              key={product.id}
              product={product}
              onAddToWatchlist={
                addedToWatchlist.has(product.id) ? undefined : handleAddToWatchlist
              }
            />
          ))}
        </div>
      )}
    </main>
  );
}
