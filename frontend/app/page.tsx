// frontend/app/page.tsx
"use client";
import { useState, useEffect, useCallback, Suspense } from "react";
import { useBaymax } from "@/lib/BaymaxContext";
import { useRouter, useSearchParams } from "next/navigation";
import { SearchBar } from "@/components/SearchBar";
import { WatchlistCard } from "@/components/WatchlistCard";
import { SearchHistory } from "@/components/SearchHistory";
import {
  getWatchlist,
  getSearchHistory,
  removeFromWatchlist,
  refreshWatchlistItem,
  deleteSearch,
} from "@/lib/api";

function HomeContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialQuery = searchParams.get("q") ?? "";
  const { setState: setBaymaxState } = useBaymax();

  const [watchlist, setWatchlist] = useState<any[]>([]);
  const [history, setHistory] = useState<any[]>([]);
  const [isRefreshingAll, setIsRefreshingAll] = useState(false);

  // Reset stale avatar state on mount/return
  useEffect(() => {
    setBaymaxState("idle");
  }, [setBaymaxState]);

  const loadData = useCallback(async () => {
    try {
      const [wl, hist] = await Promise.all([getWatchlist(), getSearchHistory()]);
      setWatchlist(wl);
      setHistory(hist);
    } catch {
      // Backend may not be running
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const AMAZON_ASIN_RE = /^https?:\/\/(www\.)?amazon\.com\/(dp|gp\/product)\/([A-Z0-9]{10})/;

  const handleSearch = (query: string) => {
    setBaymaxState("searching");
    const match = query.trim().match(AMAZON_ASIN_RE);
    if (match) {
      const asin = match[3];
      router.push(`/search/url-analysis?asin=${asin}&url=${encodeURIComponent(query.trim())}`);
      return;
    }
    router.push(`/search/preview?q=${encodeURIComponent(query)}`);
  };

  const handleDeleteWatchlist = async (id: string) => {
    await removeFromWatchlist(id);
    await loadData();
  };

  const handleRefreshWatchlist = async (id: string): Promise<void> => {
    await refreshWatchlistItem(id);
    await loadData();
  };

  const handleDeleteSearch = async (id: string) => {
    await deleteSearch(id);
    await loadData();
  };

  const handleRefreshAll = async () => {
    setIsRefreshingAll(true);
    for (const item of watchlist) {
      try {
        await refreshWatchlistItem(item.id);
      } catch {
        // continue with remaining items
      }
    }
    await loadData();
    setIsRefreshingAll(false);
  };

  return (
    <main className="min-h-screen bg-[#07070d]">
      <div className="max-w-3xl mx-auto px-4 py-12 space-y-10">
        {/* Header */}
        <div className="text-center space-y-3">
          <div className="inline-flex items-center gap-1.5 bg-[#0f0f1a] border border-[#1f1f38] text-[#818cf8] rounded-full px-3 py-1 text-[10px] font-bold tracking-widest uppercase mb-2">
            <span className="text-[#f97316]">●</span>
            AI Research
          </div>
          <h1 className="text-3xl font-black bg-clip-text text-transparent bg-gradient-to-br from-white to-[#a5b4fc]">
            Amazon Research Tool
          </h1>
          <p className="text-[#4a4a70]">AI-powered product research with review analysis</p>
        </div>

        {/* Search */}
        <SearchBar
          onSearch={handleSearch}
          isLoading={false}
          initialValue={initialQuery}
        />

        {/* Watchlist */}
        {watchlist.length > 0 && (
          <section>
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-[10px] font-bold text-[#4a4a70] uppercase tracking-widest">
                Watchlist
              </h2>
              {isRefreshingAll ? (
                <span className="text-[11px] text-[#3a3a58] pointer-events-none">
                  Refreshing...
                </span>
              ) : (
                <button
                  onClick={handleRefreshAll}
                  className="text-[11px] text-[#818cf8] underline underline-offset-2 hover:text-indigo-300 cursor-pointer"
                >
                  Refresh all
                </button>
              )}
            </div>
            <div className="space-y-2">
              {watchlist.map((item) => (
                <WatchlistCard
                  key={item.id}
                  item={item}
                  onDelete={handleDeleteWatchlist}
                  onRefresh={handleRefreshWatchlist}
                  isRefreshingAll={isRefreshingAll}
                />
              ))}
            </div>
          </section>
        )}

        {/* Search History */}
        <section>
          <h2 className="text-[10px] font-bold text-[#4a4a70] uppercase tracking-widest mb-3">
            Search History
          </h2>
          <SearchHistory items={history} onDelete={handleDeleteSearch} />
        </section>
      </div>
    </main>
  );
}

export default function HomePage() {
  return (
    <Suspense fallback={null}>
      <HomeContent />
    </Suspense>
  );
}
