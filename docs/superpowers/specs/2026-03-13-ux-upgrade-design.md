# UX Upgrade — Search Preview, Watchlist Cards & UI Overhaul

**Date:** 2026-03-13
**Status:** Approved

---

## Overview

Three connected improvements to the Amazon Research Tool frontend:

1. **Search preview step** — show web images before committing to the full Amazon scraping pipeline
2. **Watchlist card upgrade** — richer card layout with image, price, badge, price history link
3. **UI overhaul** — Direction A (Refined Dark): gradient headline, indigo accents, glowing search button

---

## 1. Search Preview Flow

### Home page changes (`page.tsx`)

The home page default export becomes a thin shell:
```tsx
export default function HomePage() {
  return (
    <Suspense fallback={null}>
      <HomeContent />
    </Suspense>
  );
}
```

All existing state (`watchlist`, `history`, `isRefreshingAll`), hooks, handlers, and JSX move into `<HomeContent />`. `HomeContent` is a `"use client"` component defined in the same file.

**New additions inside `HomeContent`:**
- `const searchParams = useSearchParams()`
- `const initialQuery = searchParams.get("q") ?? ""`
- `useEffect(() => { setBaymaxState("idle"); }, [setBaymaxState])` — resets stale Baymax state on mount/return navigation

**`handleSearch` (no try/catch — navigation is synchronous):**
```ts
const handleSearch = (query: string) => {
  setBaymaxState("searching");
  router.push(`/search/preview?q=${encodeURIComponent(query)}`);
};
```

Remove `isSearching` state and all `setIsSearching` calls. Pass `isLoading={false}` to `SearchBar` (keep the prop on `SearchBar` — it is used on the preview page).

Pass `initialValue={initialQuery}` to `SearchBar`.

**Existing functions that move unchanged into `HomeContent`:** `loadData`, `handleDeleteWatchlist`, `handleRefreshWatchlist` (calls `refreshWatchlistItem(id)` from `lib/api.ts` then `loadData()`, returns a `Promise<void>`), `handleDeleteSearch`. All three already exist in `page.tsx`.

Add `isRefreshingAll` and `handleRefreshAll` (see §2).

### `SearchBar` changes

Keep `isLoading` prop and existing internal behaviour (disables input, shows "Searching..."). Add `initialValue?: string`:
```tsx
const [query, setQuery] = useState(initialValue ?? "");
useEffect(() => { setQuery(initialValue ?? ""); }, [initialValue]);
```
The `useEffect` sync ensures the query field updates correctly on client-side navigation (e.g., returning from preview with `?q=something`). The existing `if (query.trim()) onSearch(query.trim())` guard must be preserved.

### New Page: `/search/preview`

**File:** `frontend/app/search/preview/page.tsx`

```tsx
export default function PreviewPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-[#07070d]" />}>
      <PreviewContent />
    </Suspense>
  );
}
```

**`PreviewContent` — full state and logic:**
```ts
const searchParams = useSearchParams();
const q = searchParams.get("q")?.trim() ?? "";
const router = useRouter();
const { setState: setBaymaxState } = useBaymax();
const [images, setImages] = useState<string[]>([]);
const [isLoadingImages, setIsLoadingImages] = useState(true);
const [isSubmitting, setIsSubmitting] = useState(false);
const [submitError, setSubmitError] = useState<string | null>(null);
```

**Guard effect (runs once):**
```ts
useEffect(() => {
  if (!q) router.replace("/");
}, []); // eslint-disable-line
```

**Image fetch effect:**
```ts
useEffect(() => {
  if (!q) return;
  setBaymaxState("searching");
  setIsLoadingImages(true);
  getPreviewImages(q)
    .then((result) => setImages(result.images))
    .catch(() => setImages([]))
    .finally(() => setIsLoadingImages(false));
  // Baymax stays "searching" until user clicks Yes or No
}, [q]);
```

**Loading state:** 4-column grid (`grid grid-cols-4 gap-3`) with 4 skeleton cards (`bg-[#1f1f38] animate-pulse rounded-xl aspect-square`). Confirm box rendered below with `opacity-40 pointer-events-none`.

**Loaded state — image grid (always 4 slots, `grid grid-cols-4 gap-3`):**
- Filled slots: `<div className="relative aspect-square overflow-hidden rounded-xl bg-[#1f1f38]"><img src={url} className="w-full h-full object-cover" alt="" /></div>` — plain `<img>`, not Next.js `<Image>` (untrusted external URLs)
- Empty slots: `<div className="aspect-square rounded-xl bg-[#1f1f38]" />`
- If `images.length === 0` after load: `<p className="text-[#4a4a70] text-sm text-center col-span-4 py-2">Couldn't load preview images — but you can still proceed</p>` above the all-placeholder grid

**Confirm box** (`bg-gradient-to-br from-[#0f0f1a] to-[#131325] border border-[#1f1f38] rounded-[14px] p-5`):
- Heading: "Does this look right?"
- Subtext: "Confirming will start the Amazon search and AI analysis."
- Buttons row (`flex gap-3 mt-4`):
  - "Yes" button (flex-1): `bg-gradient-to-br from-[#f97316] to-[#ea580c] shadow-[0_4px_16px_rgba(249,115,22,0.3)] rounded-[10px] py-3 text-white font-bold`
  - "No" button: `bg-[#0f0f1a] border border-[#2a2a45] rounded-[10px] py-3 px-5 text-[#818cf8] font-semibold`
- Error text below buttons (when `submitError` non-null): `<p className="text-red-400 text-sm text-center mt-2">{submitError}</p>`

**Query tag** (above the grid, below step indicator): `bg-[#0f0f1a] border border-[#2a2a45] rounded-[10px] p-3 flex items-center gap-3 mb-5`. Shows query text. "edit query" is a `<button>` styled as `text-[#818cf8] text-[11px] underline underline-offset-2 ml-auto` that triggers the "No" handler (same navigation).

Both "No, go back" button and "edit query" button share the same handler: `setBaymaxState("idle"); router.push(...)`. They are two separate UI elements — the button in the confirm box and the link in the query tag.

**"Yes" click handler:**
```ts
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
```

While `isSubmitting`: both buttons and "edit query" link disabled (`pointer-events-none opacity-60`). "Yes" button shows `⟳` with `animate-spin` class instead of check icon.

### Step indicator

`frontend/components/StepIndicator.tsx` — `"use client"`.

```tsx
const STEPS = ["Preview", "Select from Amazon", "AI Analysis"];

export function StepIndicator({ step }: { step: 1 | 2 | 3 }) {
  return (
    <div className="flex items-center gap-2 mb-6">
      {STEPS.map((label, i) => (
        <>
          <div className="flex items-center gap-1.5" key={label}>
            <div className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold ${
              i < step - 1 ? "bg-[#0a2818] text-emerald-400" :
              i === step - 1 ? "bg-[#f97316] text-white" :
              "bg-[#1a1a2e] border border-[#2a2a45] text-[#4a4a6a]"
            }`}>
              {i < step - 1 ? "✓" : i + 1}
            </div>
            <span className={`text-[11px] ${
              i < step - 1 ? "text-[#2e2e50]" :
              i === step - 1 ? "text-[#ebebf5] font-semibold" :
              "text-[#4a4a6a]"
            }`}>{label}</span>
          </div>
          {i < STEPS.length - 1 && (
            <div key={`div-${i}`} className="flex-1 h-px bg-[#1a1a2e] max-w-[48px]" />
          )}
        </>
      ))}
    </div>
  );
}
```

Past steps show `✓` (replacing the number). Active step shows the 1-based step number. 2 dividers total (between steps, no trailing).

| Page | Prop |
|---|---|
| `/search/preview` | `step={1}` |
| `/search/{id}/confirm` | `step={2}` |
| `/search/{id}/results` | `step={3}` |

### Backend: `GET /api/preview-images`

Add to `backend/main.py`. `httpx` and `re` must be imported. Add `httpx` to `backend/requirements.txt` if absent.

```python
@app.get("/api/preview-images")
async def get_preview_images(q: str):
    try:
        hdrs = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        async with httpx.AsyncClient(timeout=5.0, headers=hdrs) as client:
            r1 = await client.get(
                "https://duckduckgo.com/",
                params={"q": q, "iax": "images", "ia": "images"},
            )
            match = re.search(r"vqd=([^&'\"\s]+)", r1.text)  # note: regular string, \s matches whitespace
            if not match:
                return {"images": []}
            vqd = match.group(1)
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

`httpx` handles URL encoding of `params` dict — do not manually encode `q`.

**`getPreviewImages` in `frontend/lib/api.ts`:**
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

---

## 2. Watchlist Card Upgrade

### Existing context (no backend changes)

`refreshWatchlistItem`, `loadData`, `handleRefreshWatchlist` all already exist in `page.tsx` / `lib/api.ts`. `handleRefreshWatchlist(id)` returns `Promise<void>` (awaitable by `WatchlistCard`).

`WatchlistItem` type (existing, unchanged):
```ts
type WatchlistItem = {
  id: string;
  product: { title: string; url: string; image_url: string | null; };
  current_price: number | null;
  previous_price: number | null;
  last_checked_at: string | null;
};
```

### `WatchlistCard` — full rewrite

```tsx
type Props = {
  item: WatchlistItem;
  onDelete: (id: string) => void;
  onRefresh: (id: string) => Promise<void>;
  isRefreshingAll?: boolean;
};

export function WatchlistCard({ item, onDelete, onRefresh, isRefreshingAll }: Props) {
  const [isRefreshing, setIsRefreshing] = useState(false);
  const { product, current_price, previous_price, last_checked_at } = item;
  const priceDiff = current_price != null && previous_price != null
    ? current_price - previous_price : null;

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await onRefresh(item.id);
    setIsRefreshing(false);
  };

  const asin = product.url.match(/\/dp\/([A-Z0-9]{10})/)?.[1];
  const priceHistoryUrl = asin
    ? `https://camelcamelcamel.com/product/${asin}`
    : `https://camelcamelcamel.com/search?sq=${encodeURIComponent(product.url)}`;

  return ( /* layout below */ );
}
```

### Card layout

Outer: `bg-gradient-to-br from-[#0f0f1a] to-[#131325] border border-[#1f1f38] rounded-[14px] hover:border-[#2e2e55] transition-colors`

Inner (`flex items-center gap-3.5 p-3.5`):

**Image** (omit if `product.image_url` null): `w-[60px] h-[60px] relative flex-shrink-0 rounded-xl overflow-hidden bg-[#0a0a14] border border-[#1a1a30]` → `<Image fill unoptimized className="object-contain" />`

**Body** (`flex-1 min-w-0`):
- Name: `text-[13px] font-semibold text-[#e0e0ff] line-clamp-1 mb-1.5`
- Price row (`flex items-center gap-2`):
  - Price: `text-[18px] font-bold text-white tabular-nums` (show `"—"` if null)
  - Badge (hidden if `priceDiff === null || priceDiff === 0`):
    - `priceDiff < 0`: `bg-[#052e16] text-[#4ade80] border border-[#14532d] text-[10px] font-bold rounded-md px-1.5 py-0.5` — `↓ $${Math.abs(priceDiff).toFixed(2)} lower`
    - `priceDiff > 0`: `bg-[#2d0505] text-[#f87171] border border-[#450a0a] ...` — `↑ $${priceDiff.toFixed(2)} higher`
- Meta row (`flex items-center gap-3 mt-1`):
  - `<a href={priceHistoryUrl} target="_blank" rel="noopener noreferrer" className="text-[10px] text-[#f97316] hover:text-[#fb923c]">↗ price history</a>`
  - `<span className="text-[10px] text-[#2e2e50]">{formatLastChecked(last_checked_at)}</span>`

**Actions** (`flex flex-col gap-1.5 flex-shrink-0`), each `w-8 h-8 rounded-lg bg-[#0f0f1a] border border-[#1f1f38] flex items-center justify-center text-[#3a3a60] transition-colors`:
- Refresh `↻`: `hover:text-sky-400`; disabled + `animate-spin` text when `isRefreshing || isRefreshingAll`
- Amazon `↗` (`<a>`): `hover:text-orange-400`
- Remove `✕`: `hover:text-red-400`

Plain text characters only — no lucide-react icons.

### `formatLastChecked` — define inside `WatchlistCard.tsx` (file-level, not exported)

```ts
function formatLastChecked(ts: string | null): string {
  if (!ts) return "Never checked";
  const d = Date.now() - new Date(ts).getTime();
  if (d < 60_000) return "Just now";
  if (d < 3_600_000) return `Updated ${Math.floor(d / 60_000)}m ago`;
  if (d < 86_400_000) return `Updated ${Math.floor(d / 3_600_000)}h ago`;
  if (d < 172_800_000) return "Updated 1 day ago";
  return `Updated ${Math.floor(d / 86_400_000)} days ago`;
}
```

### Refresh all (in `HomeContent`)

```ts
const [isRefreshingAll, setIsRefreshingAll] = useState(false);

const handleRefreshAll = async () => {
  setIsRefreshingAll(true);
  for (const item of watchlist) {
    try { await refreshWatchlistItem(item.id); } catch { /* continue */ }
  }
  await loadData();
  setIsRefreshingAll(false);
};
```

Watchlist section header (`flex items-center justify-between mb-3`):
- Left: existing title style
- Right: `isRefreshingAll` → `<span className="text-[11px] text-[#3a3a58] pointer-events-none">Refreshing...</span>` else `<button onClick={handleRefreshAll} className="text-[11px] text-[#818cf8] underline underline-offset-2 hover:text-indigo-300">Refresh all</button>`

Each `<WatchlistCard>` gets `isRefreshingAll={isRefreshingAll}` and `onRefresh={handleRefreshWatchlist}`.

---

## 3. UI Overhaul — Direction A (Refined Dark)

No new npm dependencies. `animate-pulse` (Tailwind built-in) handles skeleton loading — no custom CSS keyframes needed.

### Design tokens

| Element | Value |
|---|---|
| Page bg | `bg-[#07070d]` |
| Card bg | `style={{ background: "linear-gradient(135deg, #0f0f1a, #131325)" }}` |
| Card border | `border border-[#1f1f38]` |
| Title | `bg-clip-text text-transparent bg-gradient-to-br from-white to-[#a5b4fc] font-black text-3xl` |
| AI label | `inline-flex items-center gap-1.5 bg-[#0f0f1a] border border-[#1f1f38] text-[#818cf8] rounded-full px-3 py-1 text-[10px] font-bold tracking-widest uppercase` with orange `●` span inside |
| Search wrap | `bg-[#0f0f1a] border border-[#1f1f38] rounded-[14px] p-2.5 flex gap-2.5 shadow-[0_0_0_1px_rgba(249,115,22,0.12),_0_8px_32px_rgba(0,0,0,0.6)]` |
| Search btn | `bg-gradient-to-br from-[#f97316] to-[#ea580c] shadow-[0_4px_16px_rgba(249,115,22,0.35)] rounded-[10px] px-5 py-2.5 text-white font-bold flex items-center gap-2` |
| Secondary links | `text-[#818cf8] underline underline-offset-2 hover:text-indigo-300 text-[11px] cursor-pointer` |

### Dark theme class replacements (all affected pages)

| From | To |
|---|---|
| `text-gray-900` | `text-[#ebebf5]` |
| `text-gray-700` | `text-[#ebebf5]` |
| `text-gray-500` | `text-[#7878a0]` |
| `hover:text-gray-700` | `hover:text-[#ebebf5]` |
| `text-gray-400` | `text-[#4a4a6a]` |
| `bg-white` | `bg-[#07070d]` |

**Confirm page `needsMoreDetail` branch** (lines ~56–72): `<h2>` → `text-[#ebebf5]`, `<p>` → `text-[#7878a0]`, back `<a>` → `text-[#818cf8] hover:text-indigo-300 bg-[#f97316] ...` (keep the orange button style for the CTA, fix the text link only).

**Results page:** loading div → `text-[#4a4a6a]`; `← Back` → `text-[#818cf8] hover:text-indigo-300`; `<h1>` → `text-[#ebebf5]`; product count → `text-[#4a4a6a]`; "No results found" → `text-[#4a4a6a]`.

### Affected files

| File | Action |
|---|---|
| `frontend/app/page.tsx` | Refactor to shell + `HomeContent`; all §1/§2 changes |
| `frontend/components/SearchBar.tsx` | `initialValue` prop + `useEffect` sync; glowing wrap; gradient btn; keep `isLoading` |
| `frontend/components/WatchlistCard.tsx` | Full rewrite per §2 |
| `frontend/components/StepIndicator.tsx` | New component |
| `frontend/app/search/preview/page.tsx` | New page |
| `frontend/app/search/[id]/confirm/page.tsx` | Dark theme (both branches); `<StepIndicator step={2} />` |
| `frontend/app/search/[id]/results/page.tsx` | Dark theme; `<StepIndicator step={3} />` |
| `frontend/lib/api.ts` | Add `getPreviewImages` |
| `backend/main.py` | Add `GET /api/preview-images`; add `import httpx, re` |
| `backend/requirements.txt` | Add `httpx` if absent |

---

## 4. Data Flow

```
HomePage → <Suspense><HomeContent /></Suspense>
HomeContent
  ├─ mount: setBaymaxState("idle")
  ├─ reads ?q → initialValue for SearchBar
  └─ handleSearch(q) → setBaymaxState("searching") + router.push(/search/preview?q=...)

PreviewPage → <Suspense><PreviewContent /></Suspense>
PreviewContent
  ├─ guard: !q → router.replace("/")
  ├─ mount: setBaymaxState("searching"), fetch images → stays "searching" until user acts
  ├─ Yes → setBaymaxState("thinking"), startSearch(q) → /search/{id}/confirm or error
  └─ No / edit query → setBaymaxState("idle"), router.push(/?q=...)

/search/{id}/confirm → StepIndicator step=2; dark theme fix (both branches)
/search/{id}/results → StepIndicator step=3; dark theme fix
```

---

## 5. Out of Scope

- No scraping pipeline, agent, or ranking changes
- No database schema changes
- No authentication
- DuckDuckGo fetch is best-effort; no caching, no retry
