// frontend/components/SearchBar.tsx
"use client";
import { useState, useEffect } from "react";
import { Search } from "lucide-react";

type Props = {
  onSearch: (query: string) => void;
  isLoading?: boolean;
  initialValue?: string;
};

export function SearchBar({ onSearch, isLoading, initialValue }: Props) {
  const [query, setQuery] = useState(initialValue ?? "");

  useEffect(() => {
    setQuery(initialValue ?? "");
  }, [initialValue]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) onSearch(query.trim());
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="bg-[#0f0f1a] border border-[#1f1f38] rounded-[14px] p-2.5 flex gap-2.5 shadow-[0_0_0_1px_rgba(249,115,22,0.12),_0_8px_32px_rgba(0,0,0,0.6)]"
    >
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search for a product on Amazon..."
        className="flex-1 bg-transparent border-none outline-none text-[#ebebf5] placeholder-[#2e2e50] text-[15px] px-2"
        disabled={isLoading}
      />
      <button
        type="submit"
        disabled={isLoading || !query.trim()}
        className="bg-gradient-to-br from-[#f97316] to-[#ea580c] shadow-[0_4px_16px_rgba(249,115,22,0.35)] rounded-[10px] px-5 py-2.5 text-white font-bold flex items-center gap-2 disabled:opacity-40 transition-opacity"
      >
        <Search size={16} />
        {isLoading ? "Searching..." : "Search"}
      </button>
    </form>
  );
}
