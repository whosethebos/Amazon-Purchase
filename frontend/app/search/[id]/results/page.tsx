// frontend/app/search/[id]/results/page.tsx
"use client";
import { useEffect, useState } from "react";
import { useBaymax } from "@/lib/BaymaxContext";
import { useParams } from "next/navigation";
import { ProductCard } from "@/components/ProductCard";
import { StepIndicator } from "@/components/StepIndicator";
import { getResults, addToWatchlist } from "@/lib/api";

export default function ResultsPage() {
  const { id: searchId } = useParams<{ id: string }>();
  const { setState: setBaymaxState } = useBaymax();
  const [search, setSearch] = useState<any>(null);
  const [products, setProducts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [addedToWatchlist, setAddedToWatchlist] = useState<Set<string>>(new Set());

  useEffect(() => {
    getResults(searchId)
      .then(({ search, products }) => {
        setSearch(search);
        setProducts(products);
        setBaymaxState("done");
      })
      .catch(() => setBaymaxState("error"))
      .finally(() => setLoading(false));
  }, [searchId, setBaymaxState]);

  const handleAddToWatchlist = async (productId: string) => {
    await addToWatchlist(productId);
    setAddedToWatchlist((prev) => new Set([...prev, productId]));
  };

  if (loading)
    return <div className="text-center py-16 text-[#4a4a6a]">Loading results...</div>;

  return (
    <main className="max-w-3xl mx-auto px-4 py-10 space-y-6">
      <StepIndicator step={3} />
      <div className="flex items-center gap-3 flex-wrap">
        <a href="/" className="text-sm text-[#818cf8] hover:text-indigo-300">
          ← Back
        </a>
        <h1 className="text-xl font-bold text-[#ebebf5]">
          Results: &quot;{search?.query}&quot;
        </h1>
        <span className="text-sm text-[#4a4a6a]">{products.length} products</span>
      </div>

      {products.length === 0 ? (
        <p className="text-center text-[#4a4a6a] py-16">No results found.</p>
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
