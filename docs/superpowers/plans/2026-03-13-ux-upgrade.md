# UX Upgrade Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a web image preview step before Amazon search, upgrade watchlist cards with price history links, and apply a Refined Dark UI overhaul across all pages.

**Architecture:** Backend gets a new `GET /api/preview-images` endpoint that two-step fetches DDG images; frontend gets a new `/search/preview` page inserted before the existing confirm flow; shared `StepIndicator` component ties the three-step flow together; `WatchlistCard` is fully rewritten; all pages get Direction-A dark theme tokens.

**Tech Stack:** Next.js 14 App Router, Tailwind CSS, FastAPI, httpx, Python re

**Spec:** `docs/superpowers/specs/2026-03-13-ux-upgrade-design.md`

---

## File Map

| Action | File | Responsibility |
|---|---|---|
| Modify | `backend/main.py` | Add `GET /api/preview-images` endpoint |
| Modify | `backend/requirements.txt` | Add `httpx` |
| Modify | `frontend/lib/api.ts` | Add `getPreviewImages` function |
| Create | `frontend/components/StepIndicator.tsx` | Shared 3-step progress indicator |
| Modify | `frontend/components/SearchBar.tsx` | `initialValue` prop + glowing UI |
| Create | `frontend/app/search/preview/page.tsx` | Image preview confirmation page |
| Modify | `frontend/components/WatchlistCard.tsx` | Full card rewrite with price history |
| Modify | `frontend/app/page.tsx` | Shell + HomeContent refactor, Refresh all |
| Modify | `frontend/app/search/[id]/confirm/page.tsx` | Dark theme + StepIndicator |
| Modify | `frontend/app/search/[id]/results/page.tsx` | Dark theme + StepIndicator |

---

## Chunk 1: Backend — Preview Images Endpoint

### Task 1: Add httpx dependency

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Check if httpx is already in requirements**

```bash
grep httpx backend/requirements.txt
```

Expected: either prints a line with `httpx` or no output.

- [ ] **Step 2: Add httpx if absent**

If step 1 produced no output, append to `backend/requirements.txt`:
```
httpx
```

- [ ] **Step 3: Commit**

```bash
git add backend/requirements.txt
git commit -m "chore: add httpx to backend dependencies"
```

---

### Task 2: Add `GET /api/preview-images` endpoint

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: Add imports at top of `backend/main.py`**

Add `import re` and `import httpx` to the existing import block at the top of the file. Do not duplicate if already present.

- [ ] **Step 2: Add the endpoint after the existing search endpoints (after line ~73)**

```python
@app.get("/api/preview-images")
async def get_preview_images(q: str):
    """Fetch up to 4 web image URLs for a query via DuckDuckGo (best-effort)."""
    try:
        hdrs = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        async with httpx.AsyncClient(timeout=5.0, headers=hdrs) as client:
            # Step 1: get vqd token
            r1 = await client.get(
                "https://duckduckgo.com/",
                params={"q": q, "iax": "images", "ia": "images"},
            )
            match = re.search(r"vqd=([^&'\"\s]+)", r1.text)
            if not match:
                return {"images": []}
            vqd = match.group(1)
            # Step 2: fetch image results
            r2 = await client.get(
                "https://duckduckgo.com/i.js",
                params={"q": q, "o": "json", "vqd": vqd, "f": ",,,,,", "p": "1"},
                headers={**hdrs, "Referer": "https://duckduckgo.com/"},
            )
            data = r2.json()
            images = [item["image"] for item in data.get("results", [])[:4]]
            return {"images": images}
    except Exception:
        return {"images": []}
```

- [ ] **Step 3: Verify the backend starts without errors**

```bash
cd backend && uv run uvicorn main:app --reload --port 8000
```

Expected: server starts, no import errors. Press Ctrl+C to stop.

- [ ] **Step 4: Smoke-test the endpoint**

```bash
curl "http://localhost:8000/api/preview-images?q=headphones"
```

Expected: JSON like `{"images": ["https://...","https://..."]}` or `{"images": []}` if DDG blocked. Either is acceptable — the endpoint must not 500.

- [ ] **Step 5: Commit**

```bash
git add backend/main.py backend/requirements.txt
git commit -m "feat: add GET /api/preview-images endpoint via DuckDuckGo"
```

---

### Task 3: Add `getPreviewImages` to frontend API client

**Files:**
- Modify: `frontend/lib/api.ts`

- [ ] **Step 1: Append the function to `frontend/lib/api.ts`**

```ts
export async function getPreviewImages(q: string): Promise<{ images: string[] }> {
  try {
    const res = await fetch(`${API_URL}/api/preview-images?q=${encodeURIComponent(q)}`);
    if (!res.ok) return { images: [] };
    return res.json();
  } catch {
    return { images: [] };
  }
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && bun run build 2>&1 | head -30
```

Expected: build succeeds or shows only pre-existing errors (none introduced by this change).

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/api.ts
git commit -m "feat: add getPreviewImages API client function"
```

---

## Chunk 2: Shared Components — StepIndicator + SearchBar

### Task 4: Create `StepIndicator` component

**Files:**
- Create: `frontend/components/StepIndicator.tsx`

- [ ] **Step 1: Create the file**

```tsx
// frontend/components/StepIndicator.tsx
"use client";

const STEPS = ["Preview", "Select from Amazon", "AI Analysis"];

export function StepIndicator({ step }: { step: 1 | 2 | 3 }) {
  return (
    <div className="flex items-center gap-2 mb-6">
      {STEPS.map((label, i) => (
        <div key={label} className="contents">
          <div className="flex items-center gap-1.5">
            <div
              className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold ${
                i < step - 1
                  ? "bg-[#0a2818] text-emerald-400"
                  : i === step - 1
                  ? "bg-[#f97316] text-white"
                  : "bg-[#1a1a2e] border border-[#2a2a45] text-[#4a4a6a]"
              }`}
            >
              {i < step - 1 ? "✓" : i + 1}
            </div>
            <span
              className={`text-[11px] ${
                i < step - 1
                  ? "text-[#2e2e50]"
                  : i === step - 1
                  ? "text-[#ebebf5] font-semibold"
                  : "text-[#4a4a6a]"
              }`}
            >
              {label}
            </span>
          </div>
          {i < STEPS.length - 1 && (
            <div className="flex-1 h-px bg-[#1a1a2e] max-w-[48px]" />
          )}
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && bun run build 2>&1 | head -30
```

Expected: no new errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/components/StepIndicator.tsx
git commit -m "feat: add StepIndicator shared component"
```

---

### Task 5: Update `SearchBar` with `initialValue` prop and new UI

**Files:**
- Modify: `frontend/components/SearchBar.tsx`

- [ ] **Step 1: Replace the entire file content**

```tsx
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
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && bun run build 2>&1 | head -30
```

Expected: no new errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/components/SearchBar.tsx
git commit -m "feat: upgrade SearchBar with initialValue prop and Refined Dark UI"
```

---

## Chunk 3: Search Preview Page

### Task 6: Create `/search/preview` page

**Files:**
- Create: `frontend/app/search/preview/page.tsx`

- [ ] **Step 1: Create the directory**

```bash
mkdir -p frontend/app/search/preview
```

- [ ] **Step 2: Create the file**

```tsx
// frontend/app/search/preview/page.tsx
"use client";
import { Suspense, useState, useEffect } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { useBaymax } from "@/lib/BaymaxContext";
import { getPreviewImages, startSearch } from "@/lib/api";
import { StepIndicator } from "@/components/StepIndicator";

function PreviewContent() {
  const searchParams = useSearchParams();
  const q = searchParams.get("q")?.trim() ?? "";
  const router = useRouter();
  const { setState: setBaymaxState } = useBaymax();

  const [images, setImages] = useState<string[]>([]);
  const [isLoadingImages, setIsLoadingImages] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // Guard: redirect if no query
  useEffect(() => {
    if (!q) router.replace("/");
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Fetch preview images
  useEffect(() => {
    if (!q) return;
    setBaymaxState("searching");
    setIsLoadingImages(true);
    getPreviewImages(q)
      .then((result) => setImages(result.images))
      .catch(() => setImages([]))
      .finally(() => setIsLoadingImages(false));
  }, [q]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleNo = () => {
    setBaymaxState("idle");
    router.push(`/?q=${encodeURIComponent(q)}`);
  };

  const handleConfirm = async () => {
    setIsSubmitting(true);
    setSubmitError(null);
    setBaymaxState("thinking");
    try {
      const { search_id } = await startSearch(q);
      router.push(`/search/${search_id}/confirm`);
    } catch {
      setIsSubmitting(false);
      setBaymaxState("error");
      setSubmitError("Something went wrong. Please try again.");
    }
  };

  const skeletonSlots = [0, 1, 2, 3];

  return (
    <main className="max-w-3xl mx-auto px-4 py-10 space-y-6">
      <button
        onClick={handleNo}
        className="text-sm text-[#818cf8] hover:text-indigo-300"
      >
        ← Back
      </button>

      <StepIndicator step={1} />

      {/* Query tag */}
      <div className="bg-[#0f0f1a] border border-[#2a2a45] rounded-[10px] p-3 flex items-center gap-3">
        <div>
          <p className="text-[10px] text-[#4a4a70] uppercase tracking-widest mb-0.5">Searching for</p>
          <p className="text-[15px] font-semibold text-[#ebebf5]">{q}</p>
        </div>
        <button
          onClick={handleNo}
          disabled={isSubmitting}
          className="ml-auto text-[11px] text-[#818cf8] underline underline-offset-2 hover:text-indigo-300 disabled:opacity-40"
        >
          edit query
        </button>
      </div>

      {/* Section label */}
      <p className="text-[10px] font-bold text-[#4a4a70] uppercase tracking-widest">
        Web preview — is this the right product?
      </p>

      {/* Image grid */}
      <div className="grid grid-cols-4 gap-3">
        {isLoadingImages
          ? skeletonSlots.map((n) => (
              <div key={n} className="aspect-square rounded-xl bg-[#1f1f38] animate-pulse" />
            ))
          : skeletonSlots.map((n) => {
              const url = images[n];
              return url ? (
                <div key={n} className="relative aspect-square overflow-hidden rounded-xl bg-[#1f1f38]">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={url} alt="" className="w-full h-full object-cover" />
                </div>
              ) : (
                <div key={n} className="aspect-square rounded-xl bg-[#1f1f38]" />
              );
            })}
      </div>

      {!isLoadingImages && images.length === 0 && (
        <p className="text-[#4a4a70] text-sm text-center">
          Couldn&apos;t load preview images — but you can still proceed
        </p>
      )}

      {/* Confirm box */}
      <div
        className="border border-[#1f1f38] rounded-[14px] p-5"
        style={{ background: "linear-gradient(135deg, #0f0f1a, #131325)" }}
      >
        <p className="text-[15px] font-bold text-[#ebebf5] mb-1">Does this look right?</p>
        <p className="text-[12px] text-[#7878a0] mb-4">
          Confirming will start the Amazon search and AI analysis.
        </p>
        <div className="flex gap-3">
          <button
            onClick={handleConfirm}
            disabled={isLoadingImages || isSubmitting}
            className="flex-1 bg-gradient-to-br from-[#f97316] to-[#ea580c] shadow-[0_4px_16px_rgba(249,115,22,0.3)] rounded-[10px] py-3 text-white font-bold flex items-center justify-center gap-2 disabled:opacity-40 transition-opacity"
          >
            {isSubmitting ? (
              <span className="inline-block animate-spin">⟳</span>
            ) : (
              "✓"
            )}{" "}
            Yes — Search Amazon for this
          </button>
          <button
            onClick={handleNo}
            disabled={isSubmitting}
            className="bg-[#0f0f1a] border border-[#2a2a45] rounded-[10px] py-3 px-5 text-[#818cf8] font-semibold disabled:opacity-40"
          >
            ✕ No, go back
          </button>
        </div>
        {submitError && (
          <p className="text-red-400 text-sm text-center mt-2">{submitError}</p>
        )}
      </div>
    </main>
  );
}

export default function PreviewPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-[#07070d]" />}>
      <PreviewContent />
    </Suspense>
  );
}
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd frontend && bun run build 2>&1 | head -40
```

Expected: no new errors.

- [ ] **Step 4: Start the frontend dev server and manually verify the page**

```bash
cd frontend && bun dev
```

Navigate to `http://localhost:3000/search/preview?q=headphones`. Expected: skeleton cards animate, then either real images or empty placeholders appear. Both "Yes" and "No" buttons visible.

Navigate to `http://localhost:3000/search/preview` (no `q`). Expected: immediately redirected to `/`.

- [ ] **Step 5: Commit**

```bash
git add frontend/app/search/preview/page.tsx
git commit -m "feat: add /search/preview page with image confirmation step"
```

---

## Chunk 4: Watchlist Card Rewrite

### Task 7: Rewrite `WatchlistCard` component

**Files:**
- Modify: `frontend/components/WatchlistCard.tsx`

- [ ] **Step 1: Replace the entire file**

```tsx
// frontend/components/WatchlistCard.tsx
"use client";
import { useState } from "react";
import Image from "next/image";

type WatchlistItem = {
  id: string;
  product: {
    title: string;
    url: string;
    image_url: string | null;
  };
  current_price: number | null;
  previous_price: number | null;
  last_checked_at: string | null;
};

type Props = {
  item: WatchlistItem;
  onDelete: (id: string) => void;
  onRefresh: (id: string) => Promise<void>;
  isRefreshingAll?: boolean;
};

function formatLastChecked(ts: string | null): string {
  if (!ts) return "Never checked";
  const d = Date.now() - new Date(ts).getTime();
  if (d < 60_000) return "Just now";
  if (d < 3_600_000) return `Updated ${Math.floor(d / 60_000)}m ago`;
  if (d < 86_400_000) return `Updated ${Math.floor(d / 3_600_000)}h ago`;
  if (d < 172_800_000) return "Updated 1 day ago";
  return `Updated ${Math.floor(d / 86_400_000)} days ago`;
}

export function WatchlistCard({ item, onDelete, onRefresh, isRefreshingAll }: Props) {
  const [isRefreshing, setIsRefreshing] = useState(false);
  const { product, current_price, previous_price, last_checked_at } = item;

  const priceDiff =
    current_price != null && previous_price != null
      ? current_price - previous_price
      : null;

  const asin = product.url.match(/\/dp\/([A-Z0-9]{10})/)?.[1];
  const priceHistoryUrl = asin
    ? `https://camelcamelcamel.com/product/${asin}`
    : `https://camelcamelcamel.com/search?sq=${encodeURIComponent(product.url)}`;

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await onRefresh(item.id);
    setIsRefreshing(false);
  };

  const refreshBusy = isRefreshing || !!isRefreshingAll;

  return (
    <div
      className="border border-[#1f1f38] rounded-[14px] hover:border-[#2e2e55] transition-colors"
      style={{ background: "linear-gradient(135deg, #0f0f1a, #131325)" }}
    >
      <div className="flex items-center gap-3.5 p-3.5">
        {/* Image */}
        {product.image_url && (
          <div className="w-[60px] h-[60px] relative flex-shrink-0 rounded-xl overflow-hidden bg-[#0a0a14] border border-[#1a1a30]">
            <Image
              src={product.image_url}
              alt={product.title}
              fill
              className="object-contain"
              unoptimized
            />
          </div>
        )}

        {/* Body */}
        <div className="flex-1 min-w-0">
          <p className="text-[13px] font-semibold text-[#e0e0ff] line-clamp-1 mb-1.5">
            {product.title}
          </p>

          {/* Price row */}
          <div className="flex items-center gap-2">
            <span className="text-[18px] font-bold text-white tabular-nums">
              {current_price != null ? `$${current_price.toFixed(2)}` : "—"}
            </span>
            {priceDiff != null && priceDiff !== 0 && (
              <span
                className={`text-[10px] font-bold rounded-md px-1.5 py-0.5 border ${
                  priceDiff < 0
                    ? "bg-[#052e16] text-[#4ade80] border-[#14532d]"
                    : "bg-[#2d0505] text-[#f87171] border-[#450a0a]"
                }`}
              >
                {priceDiff < 0
                  ? `↓ $${Math.abs(priceDiff).toFixed(2)} lower`
                  : `↑ $${priceDiff.toFixed(2)} higher`}
              </span>
            )}
          </div>

          {/* Meta row */}
          <div className="flex items-center gap-3 mt-1">
            <a
              href={priceHistoryUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[10px] text-[#f97316] hover:text-[#fb923c]"
            >
              ↗ price history
            </a>
            <span className="text-[10px] text-[#2e2e50]">
              {formatLastChecked(last_checked_at)}
            </span>
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex flex-col gap-1.5 flex-shrink-0">
          {/* Refresh */}
          <button
            onClick={handleRefresh}
            disabled={refreshBusy}
            title="Refresh price"
            className="w-8 h-8 rounded-lg bg-[#0f0f1a] border border-[#1f1f38] flex items-center justify-center text-[#3a3a60] hover:text-sky-400 hover:border-[#1e3a5f] transition-colors disabled:opacity-40"
          >
            <span className={refreshBusy ? "animate-spin inline-block" : ""}>↻</span>
          </button>

          {/* Open on Amazon */}
          <a
            href={product.url}
            target="_blank"
            rel="noopener noreferrer"
            className="w-8 h-8 rounded-lg bg-[#0f0f1a] border border-[#1f1f38] flex items-center justify-center text-[#3a3a60] hover:text-orange-400 transition-colors"
            title="Open on Amazon"
          >
            ↗
          </a>

          {/* Remove */}
          <button
            onClick={() => onDelete(item.id)}
            title="Remove from watchlist"
            className="w-8 h-8 rounded-lg bg-[#0f0f1a] border border-[#1f1f38] flex items-center justify-center text-[#3a3a60] hover:text-red-400 hover:border-[#7f1d1d] transition-colors"
          >
            ✕
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && bun run build 2>&1 | head -40
```

Expected: no new errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/components/WatchlistCard.tsx
git commit -m "feat: rewrite WatchlistCard with price history, badges, and refresh state"
```

---

## Chunk 5: Home Page Refactor

### Task 8: Refactor `page.tsx` into shell + `HomeContent`

**Files:**
- Modify: `frontend/app/page.tsx`

- [ ] **Step 1: Replace the entire file**

```tsx
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

  const handleSearch = (query: string) => {
    setBaymaxState("searching");
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
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && bun run build 2>&1 | head -40
```

Expected: no new errors.

- [ ] **Step 3: Manually verify the home page**

```bash
cd frontend && bun dev
```

Navigate to `http://localhost:3000`. Expected:
- Gradient title (white → indigo)
- Indigo pill "AI Research" badge with orange dot
- Glowing search bar with gradient button
- "Refresh all" link visible if watchlist has items
- Searching navigates to `/search/preview?q=...` instead of directly starting a search

- [ ] **Step 4: Commit**

```bash
git add frontend/app/page.tsx
git commit -m "feat: refactor home page with Refined Dark UI and new search preview flow"
```

---

## Chunk 6: Dark Theme Fixes + StepIndicator Integration

### Task 9: Fix dark theme and add StepIndicator to confirm page

**Files:**
- Modify: `frontend/app/search/[id]/confirm/page.tsx`

- [ ] **Step 1: Replace the entire file**

```tsx
// frontend/app/search/[id]/confirm/page.tsx
"use client";
import { useEffect, useState, useRef } from "react";
import { useBaymax } from "@/lib/BaymaxContext";
import { useParams, useRouter } from "next/navigation";
import { ConfirmationGrid } from "@/components/ConfirmationGrid";
import { ProgressFeed } from "@/components/ProgressFeed";
import { StepIndicator } from "@/components/StepIndicator";
import { useSSE } from "@/lib/useSSE";
import { confirmProducts } from "@/lib/api";

export default function ConfirmPage() {
  const { id: searchId } = useParams<{ id: string }>();
  const router = useRouter();
  const { setState: setBaymaxState } = useBaymax();
  const { events } = useSSE(searchId);
  const [currentBatch, setCurrentBatch] = useState<any[]>([]);
  const [iteration, setIteration] = useState(0);
  const [maxIterations, setMaxIterations] = useState(3);
  const [needsMoreDetail, setNeedsMoreDetail] = useState(false);
  const [isWaiting, setIsWaiting] = useState(false);
  const processedEvents = useRef(new Set<number>());

  useEffect(() => {
    events.forEach((event, idx) => {
      if (processedEvents.current.has(idx)) return;
      processedEvents.current.add(idx);

      if (event.event === "batch_ready") {
        const d = event.data as any;
        setCurrentBatch(d.batch ?? []);
        setIteration(d.iteration ?? 0);
        setMaxIterations(d.max_iterations ?? 3);
        setNeedsMoreDetail(d.needs_more_detail ?? false);
        setIsWaiting(false);
        setBaymaxState("thinking");
      }

      if (event.event === "complete") {
        setBaymaxState("done");
        router.push(`/search/${searchId}/results`);
      }
    });
  }, [events, router, searchId, setBaymaxState]);

  const handleConfirm = async (selectedIds: string[]) => {
    setIsWaiting(true);
    await confirmProducts(searchId, selectedIds);
  };

  const handleNextBatch = async () => {
    setIsWaiting(true);
    await confirmProducts(searchId, []);
  };

  if (needsMoreDetail) {
    return (
      <main className="max-w-lg mx-auto px-4 py-16 text-center space-y-4">
        <h2 className="text-xl font-semibold text-[#ebebf5]">Could not find a match</h2>
        <p className="text-[#7878a0]">
          After {iteration} attempts, we couldn&apos;t find the product you&apos;re looking for.
          Please try a more specific search query.
        </p>
        <a
          href="/"
          className="inline-block mt-4 px-5 py-2 bg-orange-500 text-white rounded-lg font-semibold hover:bg-orange-600"
        >
          ← Back to Search
        </a>
      </main>
    );
  }

  return (
    <main className="max-w-3xl mx-auto px-4 py-10 space-y-6">
      <a href="/" className="text-sm text-[#818cf8] hover:text-indigo-300">
        ← Back
      </a>
      <StepIndicator step={2} />
      <ProgressFeed events={events} />
      {isWaiting ? (
        <div className="text-center py-16 text-[#4a4a6a]">Working on it...</div>
      ) : currentBatch.length > 0 ? (
        <ConfirmationGrid
          products={currentBatch}
          iteration={iteration}
          maxIterations={maxIterations}
          onConfirm={handleConfirm}
          onNextBatch={handleNextBatch}
        />
      ) : (
        <div className="text-center py-16 text-[#4a4a6a]">Searching Amazon...</div>
      )}
    </main>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && bun run build 2>&1 | head -40
```

Expected: no new errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/search/[id]/confirm/page.tsx
git commit -m "fix: apply dark theme and StepIndicator to confirm page"
```

---

### Task 10: Fix dark theme and add StepIndicator to results page

**Files:**
- Modify: `frontend/app/search/[id]/results/page.tsx`

- [ ] **Step 1: Replace the entire file**

```tsx
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
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && bun run build 2>&1 | head -40
```

Expected: clean build.

- [ ] **Step 3: Manual end-to-end verification**

```bash
cd frontend && bun dev
```

Walk through the full flow:
1. Go to `http://localhost:3000` — confirm gradient header, glowing search bar
2. Search for "headphones" — confirm navigation to `/search/preview?q=headphones`
3. Preview page: confirm 4 image slots (skeleton then images/placeholders), step 1 active
4. Click "No, go back" — confirm return to home with "headphones" pre-filled
5. Search again, click "Yes" on preview — confirm navigation to `/search/{id}/confirm` with step 2 active
6. Results page — confirm step 3 active, dark theme throughout

- [ ] **Step 4: Final commit**

```bash
git add frontend/app/search/[id]/results/page.tsx
git commit -m "fix: apply dark theme and StepIndicator to results page"
```
