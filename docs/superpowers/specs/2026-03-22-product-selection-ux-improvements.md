# Product Selection UX Improvements Design Spec

**Date:** 2026-03-22
**Status:** Approved

## Overview

Three targeted UI improvements:
1. "Show more" lazy-load on the product selection screen (ConfirmationGrid)
2. Rename "Back" → "Home" on the results page only
3. Add Keepa price history link to ProductCard on the results page

---

## Change 1: "Show more" Lazy Load on ConfirmationGrid

### Goal
Allow users to accumulate products across multiple batches before making a selection, rather than replacing the current batch with a new one.

### Files Affected
- `frontend/app/search/[id]/confirm/page.tsx`
- `frontend/components/ConfirmationGrid.tsx`

### State Changes — `confirm/page.tsx`

| State | Type | Initial value | Change |
|---|---|---|---|
| `currentBatch` | `any[]` | `[]` | Replaced on `batch_ready` → **Appended** on `batch_ready` |
| `isLoadingMore` | `boolean` | **`false`** (new state) | `true` while "Show more" fetch is in-flight; reset to `false` on next `batch_ready` |
| `isWaiting` | `boolean` | `false` | **Unchanged** — semantics remain as-is (see note below) |

#### `isWaiting` semantics (unchanged)

`isWaiting` starts as `false`. It is only ever set `true` by an explicit user action:
- `handleConfirm` sets it `true` — hides the grid and shows `WorkflowStatus` while AI analysis runs.

It is **not** the flag for the initial load state. The initial "no products yet" state is handled separately by the `currentBatch.length === 0` branch, which renders a "Searching Amazon…" placeholder.

`isLoadingMore` is a new, separate flag that means: "a Show more fetch is in-flight, but the grid is still visible." The two flags are never both `true` at the same time.

`handleNextBatch` is **deleted**. The new `handleShowMore` uses `isLoadingMore` instead of `isWaiting`.

#### `iteration` indexing

`iteration` is **1-indexed**: the first batch arrives with `iteration = 1`, the final batch with `iteration = maxIterations`. `needs_more_detail` is `true` when `iteration >= maxIterations`.

`canShowMore` is computed as `iteration < maxIterations` — this evaluates to `false` on the final batch, which coincides with `needs_more_detail = true`.

When `needs_more_detail` becomes `true`, the orchestrator has already returned from the backend and no confirmation can be received. The existing `if (needsMoreDetail) { return <main>Could not find a match…</main> }` conditional render remains — it is the correct response, since the user cannot confirm products once the orchestrator has exited. This is unchanged behavior.

The UX improvement is that the user can confirm from the **accumulated pool** at any point across batches 1 through (n−1) — much better than the old model where each "None of these →" discarded the previous batch entirely.

#### Selection persistence

`selected` state lives inside `ConfirmationGrid` as local component state. Because `ConfirmationGrid` is never remounted between batch appends (no changing `key` prop — see implementation note), selections persist naturally across batches. This is intentional: users build their selection from the full accumulated pool.

**Implementation note:** Do **not** add a changing `key` prop to `<ConfirmationGrid>`. Doing so would unmount and remount the component, wiping the local `selected` state.

#### "Select All" scope

After accumulation, "Select All" selects all products across all appended batches. This is intentional.

### `batch_ready` Handler Change

```ts
// Before
setCurrentBatch(d.batch ?? []);
setIteration(d.iteration ?? 0);
setMaxIterations(d.max_iterations ?? 3);
setNeedsMoreDetail(d.needs_more_detail ?? false);
setIsWaiting(false);

// After
setCurrentBatch(prev => [...prev, ...(d.batch ?? [])]);  // append
setIteration(d.iteration ?? 0);
setMaxIterations(d.max_iterations ?? 3);
setNeedsMoreDetail(d.needs_more_detail ?? false);
setIsWaiting(false);
setIsLoadingMore(false);   // reset the Show more in-flight flag
```

### New Handler (replaces `handleNextBatch`)

```ts
const handleShowMore = async () => {
  setIsLoadingMore(true);
  await confirmProducts(searchId, []);
};
```

**Deleted:** `handleNextBatch` function and its `onNextBatch={handleNextBatch}` prop pass-through to `<ConfirmationGrid>`.

### `canShowMore` Computation

```ts
const canShowMore = iteration < maxIterations && !isLoadingMore;
```

Pass this as a prop to `<ConfirmationGrid>`.

### Props Changes — `ConfirmationGrid`

| Prop | Change |
|---|---|
| `onNextBatch: () => void` | **Removed** |
| `onShowMore: () => void` | Added |
| `isLoadingMore: boolean` | Added |
| `canShowMore: boolean` | Added |

### UI Changes — `ConfirmationGrid`

- **Remove** the "None of these →" button entirely.
- **Remove** the `{iteration} / {maxIterations}` counter from the heading. With accumulation, this number becomes misleading (e.g., it would show "2 / 3" even when all three batches' products are visible). Replace it with a total product count: `{products.length} products`. This prop is already available inside the component via `products.map(...)`.
- **Add** a "Show more" button in the action row, to the right of "Select All":
  - Rendered only when `canShowMore` is `true`.
  - When `isLoadingMore` is `true`: button is disabled and shows a spinner or "Loading…" label.
  - When idle: styled as a subtle text link matching the "Select All" style (`text-sm text-orange-400 hover:text-orange-300`).
- "Confirm Selected" remains disabled when `selected.size === 0`.

### Backend

No changes required. `confirmProducts(searchId, [])` already triggers the next batch; only the frontend state management changes.

### Out of Scope

If the SSE connection drops while `isLoadingMore = true`, the flag remains `true` indefinitely. This is an existing limitation of the app's SSE error handling and is not addressed by this spec.

---

## Change 2: Rename "Back" → "Home" on Results Page

### Files Affected
- `frontend/app/search/[id]/results/page.tsx` only

### Change
On the `← Back` anchor link (the `<a href="/">` near the top of the page), change the text to `← Home`. No other changes to this file.

**Explicitly excluded:** `frontend/app/search/[id]/confirm/page.tsx` also has a `← Back` link. That link navigates back to the previous step and "Back" is the correct label — it is **not** renamed.

---

## Change 3: Price History Link in ProductCard

### Goal
Surface a Keepa price history link on each product card on the results page, matching what WatchlistCard already shows.

### Files Affected
- `frontend/components/ProductCard.tsx`

### Implementation

Extract ASIN from the product URL (same regex used in `WatchlistCard`):
```ts
const asin = product.url.match(/\/dp\/([A-Z0-9]{10})/)?.[1];
```

Derive Keepa marketplace from the URL domain — **exact same order as `WatchlistCard.tsx` lines 47–55**:
```ts
const keepaMarketplace =
  product.url.includes("amazon.in")     ? 10 :
  product.url.includes("amazon.co.uk")  ? 2  :
  product.url.includes("amazon.de")     ? 3  :
  product.url.includes("amazon.fr")     ? 4  :
  product.url.includes("amazon.ca")     ? 6  :
  product.url.includes("amazon.it")     ? 8  :
  product.url.includes("amazon.es")     ? 9  :
  product.url.includes("amazon.com.au") ? 12 : 1;
  // ↑ amazon.com.au MUST be the last explicit check. The string "amazon.com"
  // is a substring of "amazon.com.au", so product.url.includes("amazon.com")
  // returns true for .com.au URLs. If an explicit "amazon.com" check were
  // inserted before this line it would shadow .com.au and assign the wrong
  // marketplace. No explicit "amazon.com" check exists in this chain or
  // should ever be added; amazon.com falls through to the default value 1.
```

```ts
const priceHistoryUrl = asin
  ? `https://keepa.com/#!product/${keepaMarketplace}-${asin}`
  : undefined;
```

**UI placement:** Add the link in the existing action row, between "View on Amazon" and "+ Watchlist":
```
[↗ View on Amazon]  [↗ price history]  [+ Watchlist]
```

- Styled identically to "View on Amazon": `text-sm text-orange-400 hover:text-orange-300`
- Only rendered when `priceHistoryUrl` is defined (ASIN found)
- Opens in a new tab (`target="_blank" rel="noopener noreferrer"`)

### No Changes Required
- No new fields on the `Product` type (ASIN is derived from `url` at render time)
- No backend changes
- No new dependencies

---

## Testing

| Scenario | Expected |
|---|---|
| First batch loads | Products shown; "Show more" visible (`iteration=1 < maxIterations`) |
| Click "Show more" | Button disabled/spinner; existing products remain; new products appended below when `batch_ready` arrives |
| After second `batch_ready` following Show more | `isLoadingMore` reset to `false`; "Show more" re-enabled if more batches remain |
| All batches exhausted (needs_more_detail=true) | "Could not find a match" screen shown; grid hidden |
| User confirms selection mid-accumulation | `isWaiting` set `true`, grid hidden, WorkflowStatus shown, AI analysis proceeds |
| Select All after multiple Show more clicks | All products across all appended batches selected |
| Results page `← Home` link | Text reads "← Home" |
| Confirm page `← Back` link | Still reads "← Back" (unchanged) |
| ProductCard on amazon.com — ASIN in URL | "↗ price history" visible; opens `keepa.com/#!product/1-{ASIN}` |
| ProductCard on amazon.in — ASIN in URL | "↗ price history" visible; opens `keepa.com/#!product/10-{ASIN}` |
| ProductCard on amazon.co.uk — ASIN in URL | "↗ price history" visible; opens `keepa.com/#!product/2-{ASIN}` |
| ProductCard — URL has no `/dp/` segment | No price history link rendered |
