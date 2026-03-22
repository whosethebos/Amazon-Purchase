# Product Selection UX Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add "Show more" lazy-loading to the product selection screen, rename "Back" to "Home" on the results page, and add a Keepa price history link to ProductCard.

**Architecture:** Three independent frontend-only changes. No backend changes, no new dependencies, no new files. The most complex change (Show more) is purely a state management update in two existing components: the page swaps `replace` for `append` in its `batch_ready` handler, and the component swaps "None of these →" for a "Show more" button.

**Tech Stack:** Next.js 16, React 19, TypeScript 5, Tailwind CSS 4. No frontend test runner is installed — TypeScript compilation (`npx tsc --noEmit`) and build (`npm run build`) serve as the validation gates.

---

## File Map

| File | Change |
|---|---|
| `frontend/app/search/[id]/results/page.tsx` | Change `← Back` link text to `← Home` |
| `frontend/components/ProductCard.tsx` | Add ASIN extraction + Keepa link in action row |
| `frontend/components/ConfirmationGrid.tsx` | Swap props; replace "None of these →" with "Show more"; replace iteration counter with product count |
| `frontend/app/search/[id]/confirm/page.tsx` | Add `isLoadingMore` state; append on `batch_ready`; add `handleShowMore`; delete `handleNextBatch`; pass new props |

---

## Task 1: Rename "Back" → "Home" on results page

**Files:**
- Modify: `frontend/app/search/[id]/results/page.tsx:41-43`

- [ ] **Step 1: Make the type-checker our canary — run tsc before touching anything**

```bash
cd /Users/whosethebos/Documents/GitHub/Amazon-Purchase/frontend
npx tsc --noEmit
```

Expected: zero errors (clean baseline). If there are pre-existing errors, note them — they are not introduced by this work.

- [ ] **Step 2: Change the link text**

In `frontend/app/search/[id]/results/page.tsx`, find the anchor tag near line 41:
```tsx
<a href="/" className="text-sm text-[#818cf8] hover:text-indigo-300">
  ← Back
</a>
```

Change to:
```tsx
<a href="/" className="text-sm text-[#818cf8] hover:text-indigo-300">
  ← Home
</a>
```

**Do not touch the identical `← Back` link in `confirm/page.tsx` — that one stays.**

- [ ] **Step 3: Verify compile**

```bash
cd /Users/whosethebos/Documents/GitHub/Amazon-Purchase/frontend
npx tsc --noEmit
```

Expected: zero errors.

- [ ] **Step 4: Commit**

```bash
cd /Users/whosethebos/Documents/GitHub/Amazon-Purchase
git add frontend/app/search/\[id\]/results/page.tsx
git commit -m "feat: rename Back to Home on results page"
```

---

## Task 2: Add Keepa price history link to ProductCard

**Files:**
- Modify: `frontend/components/ProductCard.tsx`

The `ProductCard` component already has an action row with "View on Amazon" and "+ Watchlist". We add a "↗ price history" link between them. ASIN is extracted from `product.url` (the `url` field already exists on the `Product` type at line 19). Keepa marketplace is derived from the URL domain using the same logic as `WatchlistCard.tsx`.

- [ ] **Step 1: Open `frontend/components/ProductCard.tsx` and locate the action row**

The action row starts around line 95:
```tsx
<div className="flex gap-3 pt-1">
  {/* Clicking opens Amazon URL in a new tab */}
  <a
    href={product.url}
    target="_blank"
    rel="noopener noreferrer"
    className="flex items-center gap-1 text-sm text-orange-400 hover:text-orange-300 transition-colors"
  >
    <ExternalLink size={14} /> View on Amazon
  </a>
  {onAddToWatchlist && (
    <button ...>
      <Plus size={14} /> Watchlist
    </button>
  )}
</div>
```

- [ ] **Step 2: Add ASIN extraction and Keepa URL computation inside the component body (before the return)**

Insert these lines after `const { analysis } = product;` (line 30):

```tsx
const asin = product.url.match(/\/dp\/([A-Z0-9]{10})/)?.[1];
const keepaMarketplace =
  product.url.includes("amazon.in")     ? 10 :
  product.url.includes("amazon.co.uk")  ? 2  :
  product.url.includes("amazon.de")     ? 3  :
  product.url.includes("amazon.fr")     ? 4  :
  product.url.includes("amazon.ca")     ? 6  :
  product.url.includes("amazon.it")     ? 8  :
  product.url.includes("amazon.es")     ? 9  :
  product.url.includes("amazon.com.au") ? 12 : 1;
  // amazon.com.au MUST stay last — "amazon.com" is a substring of
  // "amazon.com.au". Do NOT add an explicit amazon.com check above it.
const priceHistoryUrl = asin
  ? `https://keepa.com/#!product/${keepaMarketplace}-${asin}`
  : undefined;
```

- [ ] **Step 3: Add the link in the action row, between "View on Amazon" and Watchlist**

The updated action row:
```tsx
<div className="flex gap-3 pt-1">
  <a
    href={product.url}
    target="_blank"
    rel="noopener noreferrer"
    className="flex items-center gap-1 text-sm text-orange-400 hover:text-orange-300 transition-colors"
  >
    <ExternalLink size={14} /> View on Amazon
  </a>
  {priceHistoryUrl && (
    <a
      href={priceHistoryUrl}
      target="_blank"
      rel="noopener noreferrer"
      className="flex items-center gap-1 text-sm text-orange-400 hover:text-orange-300 transition-colors"
    >
      ↗ price history
    </a>
  )}
  {onAddToWatchlist && (
    <button
      onClick={() => onAddToWatchlist(product.id)}
      className="flex items-center gap-1 text-sm text-[#7878a0] hover:text-[#ebebf5] transition-colors"
    >
      <Plus size={14} /> Watchlist
    </button>
  )}
</div>
```

- [ ] **Step 4: Verify compile**

```bash
cd /Users/whosethebos/Documents/GitHub/Amazon-Purchase/frontend
npx tsc --noEmit
```

Expected: zero errors.

- [ ] **Step 5: Commit**

```bash
cd /Users/whosethebos/Documents/GitHub/Amazon-Purchase
git add frontend/components/ProductCard.tsx
git commit -m "feat: add Keepa price history link to ProductCard"
```

---

## Task 3: Update ConfirmationGrid — new props, updated UI

**Files:**
- Modify: `frontend/components/ConfirmationGrid.tsx`

This task updates the component's Props type and UI. It deliberately breaks the TypeScript build (the page still passes old props) — Task 4 fixes that.

- [ ] **Step 1: Update the `Props` type**

Find the `Props` type (around line 17):
```tsx
type Props = {
  products: Product[];
  iteration: number;
  maxIterations: number;
  onConfirm: (selectedIds: string[]) => void;
  onNextBatch: () => void;
};
```

Replace with:
```tsx
type Props = {
  products: Product[];
  canShowMore: boolean;
  isLoadingMore: boolean;
  onConfirm: (selectedIds: string[]) => void;
  onShowMore: () => void;
};
```

- [ ] **Step 2: Update the function signature to destructure the new props**

Find:
```tsx
export function ConfirmationGrid({ products, iteration, maxIterations, onConfirm, onNextBatch }: Props) {
```

Replace with:
```tsx
export function ConfirmationGrid({ products, canShowMore, isLoadingMore, onConfirm, onShowMore }: Props) {
```

- [ ] **Step 3: Replace the heading counter with a product count**

Find the heading section (around line 40):
```tsx
<h2 className="text-lg font-semibold text-[#ebebf5]">
  Is this the kind of product you&apos;re looking for?
  <span className="ml-2 text-sm text-[#7878a0] font-normal font-mono">
    {iteration} / {maxIterations}
  </span>
</h2>
```

Replace with:
```tsx
<h2 className="text-lg font-semibold text-[#ebebf5]">
  Is this the kind of product you&apos;re looking for?
  <span className="ml-2 text-sm text-[#7878a0] font-normal font-mono">
    {products.length} products
  </span>
</h2>
```

- [ ] **Step 4: Update the action row — remove "None of these →", add "Show more"**

Find the action row (around line 84):
```tsx
<div className="flex gap-3 pt-2">
  <button onClick={selectAll} className="text-sm text-orange-400 hover:text-orange-300 transition-colors">
    Select All
  </button>
  <div className="flex-1" />
  <button
    onClick={onNextBatch}
    className="px-4 py-2 border border-[#252530] rounded-lg text-sm text-[#7878a0] hover:border-[#353548] hover:text-[#ebebf5] transition-all"
  >
    None of these →
  </button>
  <button
    onClick={() => onConfirm([...selected])}
    disabled={selected.size === 0}
    className="px-5 py-2 bg-orange-500 text-white rounded-lg text-sm font-semibold hover:bg-orange-600 disabled:opacity-40 transition-colors"
  >
    Confirm Selected ({selected.size})
  </button>
</div>
```

Replace with:
```tsx
<div className="flex gap-3 pt-2">
  <button onClick={selectAll} className="text-sm text-orange-400 hover:text-orange-300 transition-colors">
    Select All
  </button>
  {canShowMore && (
    <button
      onClick={onShowMore}
      disabled={isLoadingMore}
      className="text-sm text-orange-400 hover:text-orange-300 transition-colors disabled:opacity-40"
    >
      {isLoadingMore ? "Loading…" : "Show more"}
    </button>
  )}
  <div className="flex-1" />
  <button
    onClick={() => onConfirm([...selected])}
    disabled={selected.size === 0}
    className="px-5 py-2 bg-orange-500 text-white rounded-lg text-sm font-semibold hover:bg-orange-600 disabled:opacity-40 transition-colors"
  >
    Confirm Selected ({selected.size})
  </button>
</div>
```

- [ ] **Step 5: Verify compile — expect errors in the confirm page (not in this file)**

```bash
cd /Users/whosethebos/Documents/GitHub/Amazon-Purchase/frontend
npx tsc --noEmit
```

Expected: TypeScript errors in `app/search/[id]/confirm/page.tsx` complaining about `onNextBatch`, `iteration`, `maxIterations` props. Errors in `ConfirmationGrid.tsx` itself: zero.

This confirms the component is correctly typed and Task 4 needs to fix the page.

- [ ] **Step 6: Commit (broken state is intentional — Task 4 completes it)**

```bash
cd /Users/whosethebos/Documents/GitHub/Amazon-Purchase
git add frontend/components/ConfirmationGrid.tsx
git commit -m "feat: update ConfirmationGrid for Show more lazy-load"
```

---

## Task 4: Update confirm/page.tsx — append batches, handle Show more

**Files:**
- Modify: `frontend/app/search/[id]/confirm/page.tsx`

This task wires up the new `ConfirmationGrid` props and changes `batch_ready` to append instead of replace.

- [ ] **Step 1: Add `isLoadingMore` state declaration**

Find the state declarations block (around line 97):
```tsx
const [isWaiting, setIsWaiting] = useState(false);
```

Add the new state immediately after:
```tsx
const [isWaiting, setIsWaiting] = useState(false);
const [isLoadingMore, setIsLoadingMore] = useState(false);
```

- [ ] **Step 2: Update the `batch_ready` handler to append and reset `isLoadingMore`**

Find the `batch_ready` block inside the `useEffect` (around line 110):
```tsx
if (event.event === "batch_ready") {
  const d = event.data as any;
  setCurrentBatch(d.batch ?? []);
  setIteration(d.iteration ?? 0);
  setMaxIterations(d.max_iterations ?? 3);
  setNeedsMoreDetail(d.needs_more_detail ?? false);
  setIsWaiting(false);
}
```

Replace with:
```tsx
if (event.event === "batch_ready") {
  const d = event.data as any;
  setCurrentBatch(prev => [...prev, ...(d.batch ?? [])]);
  setIteration(d.iteration ?? 0);
  setMaxIterations(d.max_iterations ?? 3);
  setNeedsMoreDetail(d.needs_more_detail ?? false);
  setIsWaiting(false);
  setIsLoadingMore(false);
}
```

- [ ] **Step 3: Delete `handleNextBatch` and add `handleShowMore`**

Find `handleNextBatch` (around line 130):
```tsx
const handleNextBatch = async () => {
  setIsWaiting(true);
  await confirmProducts(searchId, []);
};
```

Replace the entire function with:
```tsx
const handleShowMore = async () => {
  setIsLoadingMore(true);
  await confirmProducts(searchId, []);
};
```

- [ ] **Step 4: Compute `canShowMore` and update the `<ConfirmationGrid>` JSX**

Find the JSX section where `<ConfirmationGrid>` is used (around line 163):
```tsx
<ConfirmationGrid
  products={currentBatch}
  iteration={iteration}
  maxIterations={maxIterations}
  onConfirm={handleConfirm}
  onNextBatch={handleNextBatch}
/>
```

Replace with:
```tsx
<ConfirmationGrid
  products={currentBatch}
  canShowMore={iteration < maxIterations && !isLoadingMore}
  isLoadingMore={isLoadingMore}
  onConfirm={handleConfirm}
  onShowMore={handleShowMore}
/>
```

- [ ] **Step 5: Verify compile — zero errors expected**

```bash
cd /Users/whosethebos/Documents/GitHub/Amazon-Purchase/frontend
npx tsc --noEmit
```

Expected: zero errors. If any remain, they will name the exact line — fix before continuing.

- [ ] **Step 6: Full build check**

```bash
cd /Users/whosethebos/Documents/GitHub/Amazon-Purchase/frontend
npm run build
```

Expected: build succeeds with no errors. Ignore linting warnings unless they point to the files touched in this plan.

- [ ] **Step 7: Commit**

```bash
cd /Users/whosethebos/Documents/GitHub/Amazon-Purchase
git add frontend/app/search/\[id\]/confirm/page.tsx
git commit -m "feat: add Show more lazy-load to product selection screen"
```

---

## Manual Smoke Test Checklist

Run the app (`cd frontend && npm run dev`, backend running separately) and verify:

**Show more:**
- [ ] Search for a product. On the confirm screen, "1 products" (or count from first batch) appears in the heading.
- [ ] "Show more" button is visible to the right of "Select All".
- [ ] Clicking "Show more" disables the button and shows "Loading…".
- [ ] When the next batch arrives, new product cards appear below the existing ones. The heading product count increases.
- [ ] Selections made before clicking "Show more" are still checked.
- [ ] "Confirm Selected" stays disabled until at least one card is checked.
- [ ] Confirming a selection proceeds to the AI analysis phase normally.
- [ ] When all batches are exhausted, "Could not find a match" screen appears.

**Home link:**
- [ ] After an AI analysis completes, the results page shows "← Home" (not "← Back").
- [ ] Clicking it navigates to `/`.
- [ ] The confirm page still shows "← Back" (unchanged).

**Price history:**
- [ ] On the results page, each ProductCard has "↗ price history" between "View on Amazon" and "+ Watchlist".
- [ ] Clicking it opens `keepa.com` in a new tab with the correct ASIN.
- [ ] For an amazon.in product URL, Keepa marketplace is 10 in the URL.
