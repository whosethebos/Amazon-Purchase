# Product Selection UX Improvements Design Spec

**Date:** 2026-03-22
**Status:** Approved

## Overview

Three targeted UI improvements:
1. "Show more" lazy-load on the product selection screen (ConfirmationGrid)
2. Rename "Back" → "Home" on the results page
3. Add Keepa price history link to ProductCard on the results page

---

## Change 1: "Show more" Lazy Load on ConfirmationGrid

### Goal
Allow users to accumulate products across multiple batches before making a selection, rather than replacing the current batch with a new one.

### Files Affected
- `frontend/app/search/[id]/confirm/page.tsx`
- `frontend/components/ConfirmationGrid.tsx`

### State Changes — `confirm/page.tsx`

| State | Type | Before | After |
|---|---|---|---|
| `currentBatch` | `any[]` | Replaced on each `batch_ready` | Appended on each `batch_ready` |
| `isLoadingMore` | `boolean` | Not present | Added; `true` while awaiting next batch |

`canShowMore` is a derived value: `iteration < maxIterations && !isLoadingMore`.

**`batch_ready` handler change:**
```ts
// Before
setCurrentBatch(d.batch ?? []);

// After
setCurrentBatch(prev => [...prev, ...(d.batch ?? [])]);
setIsLoadingMore(false);
```

**New handler:**
```ts
const handleShowMore = async () => {
  setIsLoadingMore(true);
  await confirmProducts(searchId, []);
};
```

### Props Changes — `ConfirmationGrid`

| Prop | Change |
|---|---|
| `onNextBatch` | Removed |
| `onShowMore` | Added — called when "Show more" is clicked |
| `isLoadingMore` | Added — disables button and shows spinner |
| `canShowMore` | Added — hides button when no more batches exist |

### UI Changes — `ConfirmationGrid`

- **Remove** the "None of these →" button entirely.
- **Add** a "Show more" button in its place (left side of the action row, next to "Select All").
  - Visible only when `canShowMore` is true.
  - Shows a spinner / "Loading…" text when `isLoadingMore` is true.
  - Styled as a subtle text button (matching "Select All" style).
- "Confirm Selected" remains disabled when `selected.size === 0`.
- When all batches are exhausted (`!canShowMore`) and nothing is selected, the user is stuck — this is already handled by the existing `needs_more_detail` path in the backend/orchestrator, which redirects to a "Could not find a match" page.

### Backend
No changes required. `confirmProducts(searchId, [])` already triggers the next batch; only the frontend interpretation of `batch_ready` changes.

---

## Change 2: Rename "Back" → "Home" on Results Page

### Files Affected
- `frontend/app/search/[id]/results/page.tsx`

### Change
Line 41: change link text from `← Back` to `← Home`. No other changes.

---

## Change 3: Price History Link in ProductCard

### Goal
Surface a Keepa price history link on each product card on the results page, matching what WatchlistCard already shows.

### Files Affected
- `frontend/components/ProductCard.tsx`

### Implementation

Extract ASIN from the product URL (same regex already used in `WatchlistCard`):
```ts
const asin = product.url.match(/\/dp\/([A-Z0-9]{10})/)?.[1];
```

Derive Keepa marketplace from the URL domain (same logic as `WatchlistCard`):
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

const priceHistoryUrl = asin
  ? `https://keepa.com/#!product/${keepaMarketplace}-${asin}`
  : undefined;
```

**UI placement:** Add the link in the existing action row, between "View on Amazon" and "+ Watchlist":
```
[↗ View on Amazon]  [↗ price history]  [+ Watchlist]
```

- Styled identically to "View on Amazon": `text-sm text-orange-400 hover:text-orange-300`
- Only rendered when `priceHistoryUrl` is defined (i.e., ASIN was found)
- Opens in a new tab (`target="_blank" rel="noopener noreferrer"`)

### No Changes Required
- No new types on `Product`
- No backend changes
- No new dependencies

---

## Testing

| Scenario | Expected |
|---|---|
| First batch loads | Products shown, "Show more" visible if `iteration < maxIterations` |
| Click "Show more" | Spinner shown, new products appended below existing ones |
| All batches exhausted | "Show more" hidden, user must select from accumulated list |
| No products match after all batches | Existing `needs_more_detail` redirect to "Could not find" page |
| Results page loads | "Home" link text visible instead of "Back" |
| ProductCard with Amazon URL | "↗ price history" link visible, opens correct Keepa page |
| ProductCard without `/dp/` in URL | No price history link rendered |
