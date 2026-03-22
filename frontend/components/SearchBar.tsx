// frontend/components/SearchBar.tsx
"use client";
import { useState, useEffect, KeyboardEvent } from "react";
import { Search, X } from "lucide-react";

type Props = {
  onSearch: (query: string, requirements: string[]) => void;
  isLoading?: boolean;
  initialValue?: string;
  initialRequirements?: string[];
};

export function SearchBar({ onSearch, isLoading, initialValue, initialRequirements }: Props) {
  const [query, setQuery] = useState(initialValue ?? "");
  const [requirements, setRequirements] = useState<string[]>(initialRequirements ?? []);
  const [reqInput, setReqInput] = useState("");

  useEffect(() => {
    setQuery(initialValue ?? "");
  }, [initialValue]);

  useEffect(() => {
    setRequirements(initialRequirements ?? []);
  }, [initialRequirements]);

  const addTag = (value: string) => {
    const trimmed = value.trim().slice(0, 100);
    if (!trimmed) return;
    setRequirements(prev => {
      if (prev.includes(trimmed) || prev.length >= 10) return prev;
      return [...prev, trimmed];
    });
  };

  const handleReqKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      addTag(reqInput);
      setReqInput("");
    } else if (e.key === ",") {
      e.preventDefault();
      reqInput.split(",").forEach(addTag);
      setReqInput("");
    }
  };

  const removeTag = (tag: string) => {
    setRequirements(prev => prev.filter(t => t !== tag));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) onSearch(query.trim(), requirements);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-2">
      {/* Main search row */}
      <div className="bg-[#0f0f1a] border border-[#1f1f38] rounded-[14px] p-2.5 flex gap-2.5 shadow-[0_0_0_1px_rgba(249,115,22,0.12),_0_8px_32px_rgba(0,0,0,0.6)]">
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
      </div>

      {/* Requirements row */}
      <div className="bg-[#0f0f1a] border border-[#1f1f38] rounded-[14px] p-3">
        <p className="text-[10px] font-bold text-[#4a4a70] uppercase tracking-widest mb-2">
          Requirements <span className="font-normal normal-case tracking-normal">(optional)</span>
        </p>

        {/* Tags */}
        {requirements.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mb-2">
            {requirements.map(tag => (
              <span
                key={tag}
                className="inline-flex items-center gap-1 bg-[#1e1e3a] border border-[#818cf8]/30 text-[#818cf8] text-[12px] rounded-full px-2.5 py-0.5"
              >
                {tag}
                <button
                  type="button"
                  onClick={() => removeTag(tag)}
                  className="text-[#818cf8]/60 hover:text-[#818cf8] transition-colors"
                >
                  <X size={10} />
                </button>
              </span>
            ))}
          </div>
        )}

        {/* Tag input */}
        <input
          type="text"
          value={reqInput}
          onChange={(e) => setReqInput(e.target.value)}
          onKeyDown={handleReqKeyDown}
          placeholder="Type a requirement and press Enter..."
          className="w-full bg-transparent border-none outline-none text-[#ebebf5] placeholder-[#2e2e50] text-[13px]"
          disabled={isLoading}
        />
        <p className="text-[10px] text-[#2e2e50] mt-1.5">
          Press Enter or , to add · click × to remove
        </p>
      </div>
    </form>
  );
}
