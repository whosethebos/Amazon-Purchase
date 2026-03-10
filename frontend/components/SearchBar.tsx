// frontend/components/SearchBar.tsx
"use client";
import { useState } from "react";
import { Search } from "lucide-react";

type Props = {
  onSearch: (query: string) => void;
  isLoading?: boolean;
};

export function SearchBar({ onSearch, isLoading }: Props) {
  const [query, setQuery] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) onSearch(query.trim());
  };

  return (
    <form onSubmit={handleSubmit} className="flex gap-2">
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search for a product on Amazon..."
        className="flex-1 px-4 py-3 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-orange-400 text-base"
        disabled={isLoading}
      />
      <button
        type="submit"
        disabled={isLoading || !query.trim()}
        className="px-6 py-3 bg-orange-500 text-white rounded-lg font-semibold hover:bg-orange-600 disabled:opacity-50 flex items-center gap-2"
      >
        <Search size={18} />
        {isLoading ? "Searching..." : "Search"}
      </button>
    </form>
  );
}
