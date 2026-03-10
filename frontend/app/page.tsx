// frontend/app/page.tsx
"use client";
import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { SearchBar } from "@/components/SearchBar";
import { WatchlistCard } from "@/components/WatchlistCard";
import { SearchHistory } from "@/components/SearchHistory";
import {
  startSearch,
  getWatchlist,
  getSearchHistory,
  removeFromWatchlist,
  refreshWatchlistItem,
  deleteSearch,
} from "@/lib/api";

export default function HomePage() {
  const router = useRouter();
  const [isSearching, setIsSearching] = useState(false);
  const [watchlist, setWatchlist] = useState<any[]>([]);
  const [history, setHistory] = useState<any[]>([]);

  const loadData = useCallback(async () => {
    try {
      const [wl, hist] = await Promise.all([getWatchlist(), getSearchHistory()]);
      setWatchlist(wl);
      setHistory(hist);
    } catch {
      // Backend may not be running yet
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleSearch = async (query: string) => {
    setIsSearching(true);
    try {
      const { search_id } = await startSearch(query);
      router.push(`/search/${search_id}/confirm`);
    } catch (err) {
      console.error(err);
      setIsSearching(false);
    }
  };

  const handleDeleteWatchlist = async (id: string) => {
    await removeFromWatchlist(id);
    await loadData();
  };

  const handleRefreshWatchlist = async (id: string) => {
    await refreshWatchlistItem(id);
    await loadData();
  };

  const handleDeleteSearch = async (id: string) => {
    await deleteSearch(id);
    await loadData();
  };

  return (
    <main className="min-h-screen bg-gray-50">
      <div className="max-w-3xl mx-auto px-4 py-12 space-y-10">
        {/* Header */}
        <div className="text-center space-y-2">
          <h1 className="text-3xl font-bold text-gray-900">Amazon Research Tool</h1>
          <p className="text-gray-500">AI-powered product research with review analysis</p>
        </div>

        {/* Search */}
        <SearchBar onSearch={handleSearch} isLoading={isSearching} />

        {/* Watchlist */}
        {watchlist.length > 0 && (
          <section>
            <h2 className="text-lg font-semibold text-gray-800 mb-3">Watchlist</h2>
            <div className="space-y-2">
              {watchlist.map((item) => (
                <WatchlistCard
                  key={item.id}
                  item={item}
                  onDelete={handleDeleteWatchlist}
                  onRefresh={handleRefreshWatchlist}
                />
              ))}
            </div>
          </section>
        )}

        {/* Search History */}
        <section>
          <h2 className="text-lg font-semibold text-gray-800 mb-3">Search History</h2>
          <SearchHistory items={history} onDelete={handleDeleteSearch} />
        </section>
      </div>
    </main>
  );
}
