// frontend/components/ConfirmationGrid.tsx
"use client";
import { useState } from "react";
import Image from "next/image";

type Product = {
  id: string;
  title: string;
  price: number | null;
  rating: number | null;
  review_count: number | null;
  image_url: string | null;
};

type Props = {
  products: Product[];
  iteration: number;
  maxIterations: number;
  onConfirm: (selectedIds: string[]) => void;
  onNextBatch: () => void;
};

export function ConfirmationGrid({ products, iteration, maxIterations, onConfirm, onNextBatch }: Props) {
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const toggle = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const selectAll = () => setSelected(new Set(products.map((p) => p.id)));

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-800">
          Is this the kind of product you&apos;re looking for?
          <span className="ml-2 text-sm text-gray-500 font-normal">
            Batch {iteration} / {maxIterations}
          </span>
        </h2>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
        {products.map((product) => (
          <button
            key={product.id}
            onClick={() => toggle(product.id)}
            className={`text-left rounded-xl border-2 p-3 transition-all ${
              selected.has(product.id)
                ? "border-orange-500 bg-orange-50"
                : "border-gray-200 hover:border-gray-300"
            }`}
          >
            {product.image_url && (
              <div className="w-full h-40 relative mb-2 rounded-lg overflow-hidden bg-gray-100">
                <Image
                  src={product.image_url}
                  alt={product.title}
                  fill
                  className="object-contain p-2"
                  unoptimized
                />
              </div>
            )}
            <p className="text-sm font-medium text-gray-900 line-clamp-2">{product.title}</p>
            <div className="mt-1 flex items-center gap-2 text-xs text-gray-500">
              {product.price && <span className="font-semibold text-gray-800">${product.price}</span>}
              {product.rating && <span>★ {product.rating}</span>}
              {product.review_count && <span>({product.review_count.toLocaleString()})</span>}
            </div>
          </button>
        ))}
      </div>

      <div className="flex gap-3 pt-2">
        <button onClick={selectAll} className="text-sm text-orange-500 hover:underline">
          Select All
        </button>
        <div className="flex-1" />
        <button
          onClick={onNextBatch}
          className="px-4 py-2 border border-gray-300 rounded-lg text-sm hover:bg-gray-50"
        >
          None of these →
        </button>
        <button
          onClick={() => onConfirm([...selected])}
          disabled={selected.size === 0}
          className="px-5 py-2 bg-orange-500 text-white rounded-lg text-sm font-semibold hover:bg-orange-600 disabled:opacity-40"
        >
          Confirm Selected ({selected.size})
        </button>
      </div>
    </div>
  );
}
